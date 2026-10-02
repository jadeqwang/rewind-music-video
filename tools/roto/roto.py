#!/usr/bin/env python3
"""REWIND roto extractor: accepted Seedance base clip -> assets/roto/<SHOT>/ in the renderer's roto format.

  python3 tools/roto/roto.py <SHOT> [--start s --dur d] [--layers lines,matte,light,flow,face] [--workers 3]
                                    [--force] [--preview-only] [--src path.mp4] [--out name]
  python3 tools/roto/roto.py --all            # every assets/clips/*.mp4 (skips finished shots)
  python3 tools/roto/roto.py --watch E2_fast,E4,E-pull,S3,S5 --minutes 60 --every 4

Output (15 fps = the renderer's line boil on twos; 1920x1080; frame i = clip time i/15 s after --start):
  lines/NNNN.png    white RGB, alpha = stroke (vector-traced contours, anti-aliased, tapered)
  matte/NNNN.png    white RGB, alpha = the shot's PRIMARY subject (suits | jade | car), what roto.js jade()/suits() read
  mattes/NNNN.png   opaque RGB packed subject channels: R = jade, G = suits, B = car (full res; read channels in GL or
                    getImageData; never put data in alpha: createImageBitmap premultiplies)
  light/NNNN.png    opaque 960x270 atlas of two 480x270 maps. left: R = siren red, G = sodium orange, B = siren blue;
                    right: R = cold white, G = ground (grass) mask, B = scene luma (tone-normalised)
  flow/NNNN.png     opaque 240x135: R,G = motion (dx,dy) of the pixel at x since the previous drawing, in 1080p px,
                    companded: v = sign(c-128) * ((|c-128|/127)^2) * 128 ; B = 0
  face/NNNN.png     (Jade shots) white, alpha = face region where world/interior lines are suppressed
  features/NNNN.png (Jade shots) white, alpha = sparse features: lids (+ fine double-eyelid crease), iris, each brow
                    from its own landmarks (asymmetry kept), nose-tip mark, jaw contour
  hair/NNNN.png     (Jade shots) white, alpha = hair region
  face.json         (Jade shots) per frame polylines in 1080p px {eyes, brows (per side), nose, lips, jaw, iris}
  meta.json         {fps:15, frames, w:1920, h:1080, src, start, dur, layers, primary, channels, light_atlas, flow_code,
                     per_frame:[{faces:[[cx,cy,w,h]], glints:[[x,y]], mouth:[x,y,w], tilt, likeness}], timing, notes}
  preview.jpg       contact sheet (lines over black + matte tint + light map) for review
Resumable: each frame writes its PNGs (tmp + rename) and .parts/NNNN.json last; finished frames are skipped.
Parallel: the frame range is split into contiguous chunks (one per worker) so the recurrent matte model and the
flow-warped EMA run in order; a resumed chunk re-runs a few warm-up frames without writing.
"""
import os, sys, json, time, glob, argparse, subprocess, shutil, math
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import lines as LN  # noqa: E402

FPS = 15
OW, OH = 1920, 1080
LW, LH = 480, 270          # light / ground map
FW, FH = 240, 135          # flow
MODELS = os.path.join(HERE, 'models')
MODEL_URLS = {
    'rvm_mobilenetv3_fp32.onnx': 'https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx',
    'isnet-general-use.onnx': 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx',
    'efficientdet_lite2.tflite': 'https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite2/float32/latest/efficientdet_lite2.tflite',
    'face_landmarker.task': 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',
    'selfie_multiclass_256x256.tflite': 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite',
}
ALL_LAYERS = ['lines', 'matte', 'light', 'flow', 'face']
WARMUP = 5

# ---------------------------------------------------------------------------------------------------------------
# per-shot configuration. persons: which channel people go to; rvm: RVM downsample ratio (bigger = small figures);
# car: segment the car (ISNet salient object gated by EfficientDet car boxes); grass: ground mask, no lines on it;
# lines: overrides for tools/roto/lines.py DEFAULTS; sky: y fraction above which no lines (skyline dot fields)
SHOTS = {
    'E1':        dict(persons=None, sky=0.13, lines=dict(min_len=46, max_wiggle=0.08)),
    'E2_calm':   dict(persons=None),
    'E2_fast':   dict(persons=None),
    'E3_flood':  dict(persons=None),
    'E3_follow': dict(persons=None),
    'E4':        dict(persons=None, grass=True),
    'E5':        dict(persons=None),
    'E-pull':    dict(persons=None, car=True),
    'S1':        dict(persons='suits', rvm=0.4),
    'S2':        dict(persons='suits', rvm=0.4),
    'S3':        dict(persons='suits', rvm=0.7, grass=True),
    'S4':        dict(persons='suits', rvm=0.8, mgain=2.6, hold=0.996),   # seated dark suits: RVM gives soft 0.3-0.7 alpha
    'S5':        dict(persons='suits', rvm=0.4),
}


def shot_cfg(shot):
    key = shot.replace('Epull', 'E-pull').replace('E_pull', 'E-pull')
    c = dict(SHOTS.get(key, {}))
    if not c:
        if shot.startswith('J'):
            c = dict(persons='jade', rvm=0.4, face=True)
        elif shot.startswith('S'):
            c = dict(persons='suits', rvm=0.5)
        else:
            c = dict(persons=None)
    if shot.startswith('J'):
        c.setdefault('face', True)
    c.setdefault('rvm', 0.4); c.setdefault('car', False); c.setdefault('grass', False); c.setdefault('face', False)
    return c


def primary_of(cfg):
    return cfg['persons'] or ('car' if cfg['car'] else None)


def model(name):
    p = os.path.join(MODELS, name)
    if not os.path.exists(p):
        os.makedirs(MODELS, exist_ok=True)
        print('downloading', name, flush=True)
        subprocess.check_call(['curl', '-sSfL', '-o', p + '.tmp', MODEL_URLS[name]]); os.replace(p + '.tmp', p)
    return p


# ---------------------------------------------------------------------------------------------------------------
# io helpers

def write_png(path, img, level=4):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path[:-4] + '.tmp.png'
    cv2.imwrite(tmp, img, [cv2.IMWRITE_PNG_COMPRESSION, level])
    os.replace(tmp, path)


def white_alpha(a):
    a8 = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    out = np.empty(a8.shape + (4,), np.uint8); out[..., :3] = 255; out[..., 3] = a8
    return out


def to8(a):
    return np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)


def probe(src):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height,duration',
                        '-of', 'json', src], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)['streams'][0]
    return int(s['width']), int(s['height']), float(s['duration'])


def decode(src, cache, start, dur, w, h):
    """Decode at 15 fps into a raw uint8 memmap (frames, h, w, 3) BGR. Returns (memmap, n)."""
    if os.path.exists(cache + '.done'):
        n = json.load(open(cache + '.done'))['n']
        return np.memmap(cache, np.uint8, 'r', shape=(n, h, w, 3)), n
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{start:.4f}', '-i', src]
    if dur:
        cmd += ['-t', f'{dur:.4f}']
    cmd += ['-vf', f'fps={FPS}:round=near', '-f', 'rawvideo', '-pix_fmt', 'bgr24', cache + '.tmp']
    subprocess.check_call(cmd)
    n = os.path.getsize(cache + '.tmp') // (w * h * 3)
    os.replace(cache + '.tmp', cache)
    json.dump(dict(n=n), open(cache + '.done', 'w'))
    return np.memmap(cache, np.uint8, 'r', shape=(n, h, w, 3)), n


# ---------------------------------------------------------------------------------------------------------------
# models (lazy, per worker process)
_M = {}


def ort_sess(name, threads=1):
    if name not in _M:
        import onnxruntime as ort
        so = ort.SessionOptions(); so.intra_op_num_threads = threads; so.inter_op_num_threads = 1
        so.log_severity_level = 3
        _M[name] = ort.InferenceSession(model(name), so, providers=['CPUExecutionProvider'])
    return _M[name]


def mp_task(kind):
    if kind in _M:
        return _M[kind]
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision as V
    _M['mp'] = mp
    if kind == 'det':
        _M[kind] = V.ObjectDetector.create_from_options(V.ObjectDetectorOptions(
            base_options=mpt.BaseOptions(model_asset_path=model('efficientdet_lite2.tflite')), score_threshold=0.25, max_results=12))
    elif kind == 'face':
        _M[kind] = V.FaceLandmarker.create_from_options(V.FaceLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=model('face_landmarker.task')), num_faces=1,
            output_facial_transformation_matrixes=True, output_face_blendshapes=True, min_face_detection_confidence=0.3))
    elif kind == 'seg':
        _M[kind] = V.ImageSegmenter.create_from_options(V.ImageSegmenterOptions(
            base_options=mpt.BaseOptions(model_asset_path=model('selfie_multiclass_256x256.tflite')), output_confidence_masks=True))
    return _M[kind]


def mp_image(bgr):
    mp = _M['mp']
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(bgr[..., ::-1]))


def brighten(bgr, tn):
    """Lift dark plates for the ML models (same per-shot gamma as the line tone)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = np.clip(lab[..., 0].astype(np.float32) / 255 / tn['hi'], 0, 1) ** tn['gamma']
    lab[..., 0] = to8(L)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


class RVM:
    def __init__(self, ratio):
        self.s = ort_sess('rvm_mobilenetv3_fp32.onnx', 1)
        self.ratio = np.array([ratio], np.float32); self.reset()

    def reset(self):
        self.rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4

    def __call__(self, bgr):
        src = (bgr[..., ::-1].astype(np.float32) / 255).transpose(2, 0, 1)[None]
        out = self.s.run(None, {'src': src, 'r1i': self.rec[0], 'r2i': self.rec[1], 'r3i': self.rec[2], 'r4i': self.rec[3],
                                'downsample_ratio': self.ratio})
        self.rec = out[2:]
        return out[1][0, 0]


def isnet(bgr):
    s = ort_sess('isnet-general-use.onnx', 1)
    x = cv2.resize(bgr[..., ::-1], (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 - 0.5
    o = s.run(None, {s.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    o = (o - o.min()) / (o.max() - o.min() + 1e-6)
    return cv2.resize(o, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)


def car_boxes(bgr):
    r = mp_task('det').detect(mp_image(bgr))
    out = []
    for d in r.detections:
        c = d.categories[0]
        if c.category_name in ('car', 'truck', 'bus', 'train') and c.score >= 0.3:
            b = d.bounding_box; out.append((b.origin_x, b.origin_y, b.origin_x + b.width, b.origin_y + b.height, c.score))
    return out


# ---------------------------------------------------------------------------------------------------------------
# per-frame analyses

def warp(img, flow_back):
    """Warp the previous frame's map into the current frame: flow_back(x) = where pixel x was in the previous frame
    (in img's pixel units)."""
    h, w = img.shape[:2]
    fb = cv2.resize(flow_back, (w, h), interpolation=cv2.INTER_LINEAR) * np.array([w / flow_back.shape[1], h / flow_back.shape[0]], np.float32)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + fb[..., 0], gy + fb[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def light_maps(bgr, tn):
    """Hue floods at LWxLH: red, sodium, blue, white (0..1) + tone-normalised luma."""
    s = cv2.resize(bgr, (LW, LH), interpolation=cv2.INTER_AREA)
    s = cv2.GaussianBlur(s, (0, 0), 1.2)
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    H = hsv[..., 0] * (360 / 256); S = hsv[..., 1] / 255; V = hsv[..., 2] / 255
    Vn = np.clip(V / max(0.2, tn['hi']), 0, 1)
    ramp = lambda x, a, b: np.clip((x - a) / (b - a), 0, 1)
    def hue_band(c, half, soft=10):
        d = np.abs((H - c + 180) % 360 - 180)
        return np.clip(1 - (d - half) / soft, 0, 1)
    sat = ramp(S, 0.35, 0.6)
    val = ramp(Vn, 0.12, 0.6)
    red = np.maximum(hue_band(0, 14), hue_band(345, 8)) * sat * val
    sod = hue_band(32, 14) * sat * val
    blue = np.maximum(hue_band(228, 28), hue_band(270, 12) * 0.8) * sat * val
    white = (1 - ramp(S, 0.18, 0.35)) * ramp(Vn, 0.6, 0.92)
    luma = np.clip(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255 / tn['hi'], 0, 1) ** tn['gamma']
    return red, sod, blue, white, luma


def ground_mask(bgr, tn):
    """Grass: dense fine texture below the horizon (LWxLH, 0..1). Columns are filled from the first textured row down."""
    g = cv2.cvtColor(cv2.resize(bgr, (LW * 2, LH * 2), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    g = np.clip(g / tn['hi'], 0, 1) ** tn['gamma']
    hp = g - cv2.GaussianBlur(g, (0, 0), 2.0)
    e = cv2.GaussianBlur(np.abs(hp), (0, 0), 6)
    e = cv2.resize(e, (LW, LH), interpolation=cv2.INTER_AREA)
    t = (e > max(0.012, np.percentile(e, 60) * 0.8)).astype(np.uint8)
    t = cv2.morphologyEx(t, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    t = cv2.morphologyEx(t, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # fill each column below its first textured row that has texture under it for >= 25% of the remaining height
    m = np.zeros_like(t)
    cs = np.cumsum(t[::-1], 0)[::-1]           # textured rows at or below y
    rem = np.arange(LH, 0, -1)[:, None]
    ok = (t > 0) & (cs >= 0.5 * rem) & (np.arange(LH)[:, None] > LH * 0.2)
    first = np.where(ok.any(0), ok.argmax(0), LH)
    first = cv2.GaussianBlur(first.astype(np.float32)[None], (0, 0), 6)[0]
    m = (np.arange(LH)[:, None] >= first[None]).astype(np.float32)
    return cv2.GaussianBlur(m, (0, 0), 1.5)


def heads_from_matte(m, min_area_frac=0.002):
    """Face bars for REDACTION suits: for each person blob, find head peaks on its top contour; the bar sits at eye
    level. Returns ([[cx,cy,w,h]], [[gx,gy]]) in 1080p px (m is the 1080p matte, 0..1)."""
    s = 4
    b = (cv2.resize(m, (OW // s, OH // s), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b)
    faces, glints = [], []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < min_area_frac * b.size:
            continue
        sub = lab[y:y + h, x:x + w] == i
        top = np.where(sub.any(0), sub.argmax(0), h).astype(np.float32)
        top_s = cv2.GaussianBlur(top[None], (0, 0), 2)[0] if w > 4 else top
        # head width estimate: a head is ~0.17 of the blob height for a standing figure, at least 4 px
        hw = max(4, int(min(h * 0.17, w * 0.45)))
        peaks = []
        for cx in range(w):
            lo, hi = max(0, cx - hw), min(w, cx + hw + 1)
            if top_s[cx] <= top_s[lo:hi].min() + 1e-3 and top_s[cx] < h:
                if not peaks or cx - peaks[-1] > hw:
                    peaks.append(cx)
        for cx in peaks:
            ty = top_s[cx]
            # head width: run of mask across the row ~0.5 head below the top
            yy = int(min(h - 1, ty + hw * 0.6))
            row = sub[yy]
            l = cx
            while l > 0 and row[l - 1]: l -= 1
            r = cx
            while r < w - 1 and row[r + 1]: r += 1
            hwid = max(3, min(r - l + 1, int(hw * 1.6)))
            if ty > top_s.min() + h * 0.5:      # a 'peak' low on the blob is a shoulder/arm, not a head
                continue
            hh = hwid * 1.3
            fcx, fcy = (x + (l + r) / 2) * s, (y + ty + hh * 0.58) * s
            faces.append([round(fcx, 1), round(fcy, 1), round(hwid * s, 1), round(hh * 0.3 * s, 1)])
            glints.append([round(fcx, 1), round(fcy, 1)])
    return faces, glints


# face (Jade shots): tools/roto/face.py (template eyes, footage anchors)
import face as FC  # noqa: E402


def likeness_gate(bgr_full):
    try:
        sys.path.insert(0, os.path.join(ROOT, 'tools', 'likeness'))
        import measure as LM
        m = LM.measure(np.ascontiguousarray(bgr_full[..., ::-1]))
        if m is None:
            return None
        ok, devs, _ = LM.gate(m)
        return dict(ok=bool(ok), devs={k: v for k, v in devs.items()})
    except Exception as e:  # the gate is advisory here; never fail the roto on it
        return dict(ok=None, err=str(e)[:120])


# ---------------------------------------------------------------------------------------------------------------
# worker

def flow_encode(fx, fy):
    def c(v):
        return np.clip(128 + 127 * np.sign(v) * np.sqrt(np.clip(np.abs(v), 0, 128) / 128), 0, 255)
    out = np.zeros((FH, FW, 3), np.uint8); out[..., 2] = to8(np.zeros(1))[0]
    out[..., 2] = c(fx).astype(np.uint8); out[..., 1] = c(fy).astype(np.uint8); out[..., 0] = 0   # BGR: R=dx, G=dy
    return out


def _jd(o):
    return o.tolist() if hasattr(o, 'tolist') else float(o)


def run_chunk(job):
    cv2.setNumThreads(1)
    shot, d, cache, shape, n, i0, i1, layers, cfg, tn, force = job
    h, w = shape
    frames = np.memmap(cache, np.uint8, 'r', shape=(n, h, w, 3))
    done = lambda i: os.path.exists(f'{d}/.parts/{i:04d}.json')
    todo = [i for i in range(i0, i1) if force or not done(i)]
    if not todo:
        return []
    first = todo[0]
    s0 = max(0, first - WARMUP)          # warm-up frames may come from the previous chunk (flow, EMA, RVM state)
    rvm = RVM(cfg['rvm']) if ('matte' in layers and cfg['persons']) else None
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    prev_g = None; ema = {}; car_box = None; car_box_age = 99; stats = []; trk = None
    lp = cfg.get('lines', {})
    for i in range(s0, i1):
        write = (i >= first) and (force or not done(i))
        T = {}; t0 = time.time()
        src = np.ascontiguousarray(frames[i])
        big = cv2.resize(src, (OW, OH), interpolation=cv2.INTER_LANCZOS4) if (src.shape[1], src.shape[0]) != (OW, OH) else src
        # flow (previous drawing -> this one), at 480x270 on the tone-lifted luma
        g = cv2.cvtColor(cv2.resize(src, (LW, LH), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        g = to8(np.clip(g.astype(np.float32) / 255 / tn['hi'], 0, 1) ** tn['gamma'])
        if prev_g is not None:
            fb = dis.calc(g, prev_g, None)              # for each pixel now: offset to where it was
        else:
            fb = np.zeros((LH, LW, 2), np.float32)
        prev_g = g
        T['flow'] = time.time() - t0
        pf = {}
        # mattes
        t = time.time()
        ch = {}
        if 'matte' in layers:
            if rvm is not None:
                a = rvm(brighten(src, tn))
                if cfg.get('mgain', 1) != 1:
                    a = np.clip(a * cfg['mgain'], 0, 1)
                a = cv2.resize(a, (OW, OH), interpolation=cv2.INTER_CUBIC)
                ch[cfg['persons']] = a
            if cfg['car']:
                bx = car_boxes(brighten(src, tn))
                if bx:
                    car_box = max(bx, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]) * b[4]); car_box_age = 0
                else:
                    car_box_age += 1
                if car_box is not None and car_box_age < 8:
                    if i % 2 == 1 and ema.get('_sal') is not None:   # ISNet (~5-9 s single-threaded) on every other drawing
                        sal = warp(ema['_sal'], fb)
                    else:
                        sal = isnet(brighten(src, tn))
                    ema['_sal'] = sal
                    x0, y0, x1, y1, _ = car_box
                    gate = np.zeros(sal.shape, np.float32)
                    mx, my = 0.12 * (x1 - x0), 0.12 * (y1 - y0)
                    gate[max(0, int(y0 - my)):int(y1 + my), max(0, int(x0 - mx)):int(x1 + mx)] = 1
                    gate = cv2.GaussianBlur(gate, (0, 0), 6)
                    a = cv2.resize(np.clip((sal - 0.3) / 0.4, 0, 1) * gate, (OW, OH), interpolation=cv2.INTER_CUBIC)
                else:
                    a = np.zeros((OH, OW), np.float32)
                if 'suits' in ch:
                    a = a * (1 - ch['suits'])
                ch['car'] = a
            # temporal smoothing: flow-warped EMA (kills flicker, keeps motion), then edge snap to the 1080p frame
            guide = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
            for k, a in list(ch.items()):
                alpha_new = 0.65 if k != 'car' else 0.45
                if k in ema:
                    wp = warp(ema[k], fb)
                    a = alpha_new * a + (1 - alpha_new) * wp
                    if cfg.get('hold') and k != 'car':      # static seated figures fade out of RVM: hold what was seen
                        a = np.maximum(a, wp * cfg['hold'])
                ema[k] = a
                r = cv2.ximgproc.guidedFilter(guide, a.astype(np.float32), 3, 1e-3)
                ch[k] = np.clip((r - 0.5) * 1.6 + 0.5, 0, 1)        # firm the edge after the soft filter
        T['matte'] = time.time() - t
        # ground (grass shots)
        t = time.time()
        ground = None
        if cfg['grass']:
            ground = ground_mask(src, tn)
            if 'ground' in ema:
                ground = 0.6 * ground + 0.4 * warp(ema['ground'], fb)
            ema['ground'] = ground
        T['ground'] = time.time() - t
        # face (Jade)
        t = time.time(); fx = None
        if 'face' in layers and cfg['face']:
            if trk is None:
                trk = FC.FaceTracker(shot, OW / w)
            fx = FC.face_layers(big, src, trk, i)
            if fx['mouth']:
                pf['mouth'] = fx['mouth']; pf['tilt'] = fx['tilt']
            pf['face_mode'] = fx['mode']
            if fx['mouth_open'] is not None:
                pf['mouth_open_raw'] = fx['mouth_open']
            if write and i % 3 == 0:
                pf['likeness'] = likeness_gate(big)
        T['face'] = time.time() - t
        # lines (suppressed on the ground and inside the face)
        t = time.time()
        if 'lines' in layers:
            sup = np.zeros((LN.AH, LN.AW), np.float32)
            if ground is not None:
                sup = np.maximum(sup, cv2.dilate(cv2.resize(ground, (LN.AW, LN.AH)), np.ones((5, 5), np.uint8)))
                if 'suits' in ch:   # keep the figures' contours inside the grass
                    sup = sup * (1 - cv2.resize(ch['suits'], (LN.AW, LN.AH)))
            if fx is not None:
                sup = np.maximum(sup, cv2.resize(fx['face'], (LN.AW, LN.AH)))
            if cfg.get('sky'):
                sup[:int(cfg['sky'] * LN.AH)] = 1
            pm = None
            if '_lines' in ema:
                pm = cv2.dilate((warp(ema['_lines'].astype(np.float32), fb) > 0.5).astype(np.uint8), np.ones((5, 5), np.uint8))
            al, info = LN.extract(src, tn, lp, suppress=sup, prev=pm)
            ema['_lines'] = info['mask']
            pf['strokes'] = info['n']
            if fx is not None and cfg.get('glasses', False) and fx['poly'] is not None:
                gz = fx['glasses']
                ga, _ = LN.extract(src, tn, {**lp, 'min_len': 26, 'min_len_closed': 40, 'min_strength': 0.16, 'coarse': False,
                                            'pointlights': False, 'skyline': False, 'w_min': 1.4, 'w_max': 2.2},
                                   suppress=1 - cv2.resize(gz, (LN.AW, LN.AH)))
                fx['features'] = np.maximum(fx['features'], ga * gz)
        T['lines'] = time.time() - t
        if not write:
            continue
        t = time.time()
        if 'lines' in layers:
            write_png(f'{d}/lines/{i:04d}.png', white_alpha(al))
        if 'matte' in layers and ch:
            prim = primary_of(cfg)
            if prim in ch:
                write_png(f'{d}/matte/{i:04d}.png', white_alpha(ch[prim]))
            packed = np.zeros((OH, OW, 3), np.uint8)
            for k, c in (('jade', 2), ('suits', 1), ('car', 0)):    # BGR order: R=jade, G=suits, B=car
                if k in ch:
                    packed[..., c] = to8(ch[k])
            write_png(f'{d}/mattes/{i:04d}.png', packed)
            if cfg['persons'] == 'suits' and 'suits' in ch:
                pf['faces'], pf['glints'] = heads_from_matte(ch['suits'])
        if 'light' in layers:
            red, sod, blue, white, luma = light_maps(src, tn)
            gm = ground if ground is not None else np.zeros((LH, LW), np.float32)
            atlas = np.zeros((LH, LW * 2, 3), np.uint8)
            atlas[:, :LW, 2], atlas[:, :LW, 1], atlas[:, :LW, 0] = to8(red), to8(sod), to8(blue)
            atlas[:, LW:, 2], atlas[:, LW:, 1], atlas[:, LW:, 0] = to8(white), to8(gm), to8(luma)
            write_png(f'{d}/light/{i:04d}.png', atlas)
            pf['light'] = [round(float(x.mean()), 4) for x in (red, sod, blue, white)]
        if 'flow' in layers:
            v = -fb * (OW / LW)                                      # velocity of the pixel at x, 1080p px per drawing
            v = cv2.resize(v, (FW, FH), interpolation=cv2.INTER_AREA)
            write_png(f'{d}/flow/{i:04d}.png', flow_encode(v[..., 0], v[..., 1]))
        if fx is not None:
            write_png(f'{d}/face/{i:04d}.png', white_alpha(fx['face']))
            write_png(f'{d}/features/{i:04d}.png', white_alpha(fx['features']))
            write_png(f'{d}/hair/{i:04d}.png', white_alpha(fx['hair']))
            pf['poly'] = fx['poly']
        T['write'] = time.time() - t
        T['total'] = time.time() - t0
        pf['t'] = {k: round(v, 3) for k, v in T.items()}
        pf['layers'] = layers
        os.makedirs(f'{d}/.parts', exist_ok=True)
        json.dump(pf, open(f'{d}/.parts/{i:04d}.tmp', 'w'), default=_jd); os.replace(f'{d}/.parts/{i:04d}.tmp', f'{d}/.parts/{i:04d}.json')
        stats.append(T['total'])
        if i % 10 == 0:
            print(f'  {shot} {i:4d}/{n} {T["total"]:.2f}s  ' + ' '.join(f'{k}={v:.2f}' for k, v in T.items() if k != 'total'), flush=True)
    return stats


# ---------------------------------------------------------------------------------------------------------------
# preview

PAL = dict(red=(42, 42, 255), sod=(28, 159, 255), blue=(255, 91, 47), white=(216, 230, 236),
           jade=(216, 230, 236), suits=(255, 140, 60), car=(80, 220, 80))


def preview(d, meta, n_tiles=8, src_frames=None):
    n = meta['frames']
    idx = sorted(set(int(round(x)) for x in np.linspace(0, n - 1, n_tiles)))
    tiles = []
    tw, th = 640, 360
    for i in idx:
        tile = np.zeros((th, tw, 3), np.float32)
        lp = f'{d}/light/{i:04d}.png'
        if os.path.exists(lp):
            at = cv2.imread(lp).astype(np.float32) / 255
            L, Rr = at[:, :LW], at[:, LW:]
            for c, key in ((L[..., 2], 'red'), (L[..., 1], 'sod'), (L[..., 0], 'blue'), (Rr[..., 2], 'white')):
                tile += cv2.resize(c, (tw, th))[..., None] * (np.array(PAL[key], np.float32) / 255) * (0.45 if key != 'white' else 0.25)
        if os.path.exists(lp) and meta.get('cfg', {}).get('grass'):
            gm = cv2.resize(at[:, LW:, 1], (tw, th))[..., None]
            tile = tile * (1 - 0.35 * gm) + 0.35 * gm * np.array([0.25, 0.75, 0.3], np.float32)
        mp_ = f'{d}/mattes/{i:04d}.png'
        if os.path.exists(mp_):
            mm = cv2.resize(cv2.imread(mp_), (tw, th), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            for c, key in ((2, 'jade'), (1, 'suits'), (0, 'car')):
                a = mm[..., c][..., None] * 0.55
                tile = tile * (1 - a) + a * (np.array(PAL[key], np.float32) / 255) * 0.6
        for lay, col, k in (('features', (60, 60, 255), 1.0), ('lines', (255, 255, 255), 1.0)):
            p = f'{d}/{lay}/{i:04d}.png'
            if os.path.exists(p):
                a = cv2.resize(cv2.imread(p, cv2.IMREAD_UNCHANGED)[..., 3], (tw, th), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
                tile = tile * (1 - a[..., None]) + a[..., None] * np.array(col, np.float32) / 255
        pf = meta['per_frame'][i] if i < len(meta['per_frame']) else {}
        k = tw / OW
        for f in pf.get('faces', []) or []:
            cx, cy, fw, fh = f
            cv2.rectangle(tile, (int((cx - fw * 0.775) * k), int((cy - fh / 2) * k)), (int((cx + fw * 0.775) * k), int((cy + fh / 2) * k)), (0.1, 0.1, 0.1), -1)
            cv2.rectangle(tile, (int((cx - fw * 0.775) * k), int((cy - fh / 2) * k)), (int((cx + fw * 0.775) * k), int((cy + fh / 2) * k)), (0.5, 0.5, 0.5), 1)
        t8 = to8(np.clip(tile, 0, 1))
        if src_frames is not None and i < len(src_frames):
            th_ = cv2.resize(np.asarray(src_frames[i]), (160, 90), interpolation=cv2.INTER_AREA)
            t8[th - 92:th - 2, tw - 162:tw - 2] = th_
        cv2.putText(t8, f'{meta["shot"]} #{i} t={i / FPS:.2f}s', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        tiles.append(t8)
    while len(tiles) % 4:
        tiles.append(np.zeros((th, tw, 3), np.uint8))
    rows = [np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]
    sheet = np.vstack(rows)
    cv2.imwrite(f'{d}/preview.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 86])


# ---------------------------------------------------------------------------------------------------------------

def process(shot, start=0.0, dur=None, layers=None, workers=3, force=False, src=None, out=None, preview_only=False):
    from multiprocessing import get_context
    src = src or os.path.join(ROOT, 'assets', 'clips', f'{shot}.mp4')
    name = out or shot
    d = os.path.join(ROOT, 'assets', 'roto', name)
    cfg = shot_cfg(shot)
    layers = layers or [l for l in ALL_LAYERS if l != 'face' or cfg['face']]
    w, h, sdur = probe(src)
    dur = dur if dur else max(0.0, sdur - start)
    os.makedirs(d, exist_ok=True)
    cache = os.path.join(d, f'.src_{start:.2f}_{dur:.2f}.u8')
    frames, n = decode(src, cache, start, dur, w, h)
    # per-shot tone from 8 sample frames (stable over time)
    smp = [cv2.cvtColor(cv2.resize(np.asarray(frames[j]), (LN.AW, LN.AH), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB)[..., 0]
           for j in np.linspace(0, n - 1, min(8, n)).astype(int)]
    tn = LN.shot_tone(smp)
    t0 = time.time()
    stats = []
    if not preview_only:
        k = max(1, min(workers, n // 8 or 1))
        if cfg.get('hold') or (cfg['face'] and 'face' in layers):
            k = 1          # the matte hold / face tracker need the whole history in one process
        bounds = np.linspace(0, n, k + 1).astype(int)
        jobs = [(shot, d, cache, (h, w), n, int(bounds[j]), int(bounds[j + 1]), layers, cfg, tn, force) for j in range(k)]
        print(f'{shot}: {n} frames @15fps from {os.path.relpath(src, ROOT)} ({w}x{h}), layers={layers}, workers={k}, tone={tn}', flush=True)
        if k == 1:
            stats = run_chunk(jobs[0])
        else:
            with get_context('spawn').Pool(k) as pool:
                for s in pool.map(run_chunk, jobs):
                    stats += s
    wall = time.time() - t0
    # merge meta
    per = []
    for i in range(n):
        p = f'{d}/.parts/{i:04d}.json'
        per.append(json.load(open(p)) if os.path.exists(p) else {})
    tsum = {}
    for p in per:
        for kk, v in (p.get('t') or {}).items():
            tsum.setdefault(kk, []).append(v)
    face_poly = [p.pop('poly', None) for p in per] if cfg['face'] else None
    if cfg['face']:
        mouth_track(per, src, start, cfg.get('lip_lead', 0.29))
    prim = primary_of(cfg)
    lay_out = []
    if 'lines' in layers: lay_out.append('lines')
    if 'matte' in layers and prim: lay_out += ['matte', 'mattes']
    if 'light' in layers: lay_out.append('light')
    if 'flow' in layers: lay_out.append('flow')
    if 'face' in layers and cfg['face']: lay_out += ['face', 'features', 'hair']
    old = {}
    if os.path.exists(f'{d}/meta.json'):
        try: old = json.load(open(f'{d}/meta.json'))
        except Exception: old = {}
    gate_flags = [i for i, p in enumerate(per) if (p.get('likeness') or {}).get('ok') is False]
    meta = dict(shot=shot, fps=FPS, frames=n, w=OW, h=OH, src=os.path.relpath(src, ROOT), start=start, dur=round(n / FPS, 3),
                layers=lay_out, primary=prim, channels=dict(R='jade', G='suits', B='car'),
                light_atlas=dict(size=[LW * 2, LH], left=dict(R='siren_red', G='sodium', B='siren_blue'),
                                 right=dict(R='cold_white', G='ground', B='luma')),
                flow_code=dict(size=[FW, FH], units='px@1920x1080 per drawing (1/15 s), motion of the pixel at x since the previous drawing',
                               decode='v = sign(c-128)*((|c-128|/127)^2)*128', R='dx', G='dy'),
                tone=tn, cfg={k: v for k, v in cfg.items()},
                per_frame=[{k: v for k, v in p.items() if k not in ('t', 'layers')} for p in per],
                timing=dict(sec_per_frame_mean={k: round(float(np.mean(v)), 3) for k, v in tsum.items()},
                            wall_s=round(wall, 1) if stats else old.get('timing', {}).get('wall_s'), workers=workers),
                likeness_flags=gate_flags,
                notes='tools/roto/roto.py; lines vector-traced (FGS-flattened luma, Canny+band-pass, path cleanup); '
                      'mattes RVM (persons) / ISNet x EfficientDet (car), flow-warped EMA + guided edge snap')
    json.dump(meta, open(f'{d}/meta.json', 'w'))
    if face_poly is not None:
        json.dump(face_poly, open(f'{d}/face.json', 'w'))
    preview(d, meta, src_frames=frames)
    complete = all(per)
    if complete and os.path.exists(cache):
        os.remove(cache); os.remove(cache + '.done')
    sz = sum(os.path.getsize(p) for p in glob.glob(f'{d}/**/*.png', recursive=True))
    print(f'{shot}: done {sum(1 for p in per if p)}/{n} frames, wall {wall:.1f}s, {sz / 1e6:.1f} MB, '
          f'mean s/frame (per worker): ' + ', '.join(f'{k}={v}' for k, v in meta['timing']['sec_per_frame_mean'].items()), flush=True)
    return meta


def mouth_track(per, src, start, lead):
    """Footage mouth openness, shifted +lead s (Seedance lip-sync leads the audio by ~0.29 s): mouth_open[i] =
    raw(t_i - lead). raw = inner-lip gap / IOD from landmarks; profile frames use tools/likeness/lipsync.py's tracked
    dark-gap series (assets/gen/<clip>_lipsync.json) when present. The renderer's vocal envelope stays the primary
    mouth driver; this is the footage track for reference / blending."""
    import re
    n = len(per); t = start + np.arange(n) / FPS
    raw = np.array([p.get('mouth_open_raw', np.nan) for p in per], float)
    base = re.sub(r'_[0-9a-f]{10}$', '', os.path.splitext(os.path.basename(src))[0])
    lj = os.path.join(os.path.dirname(src), base + '_lipsync.json')
    src_kind = 'landmarks'
    if os.path.exists(lj) and np.isfinite(raw).mean() < 0.5:
        L = json.load(open(lj)); ms = np.array(L['mouth'], float); tf = np.arange(len(ms)) / L.get('fps', 24)
        lo, hi = np.nanpercentile(ms, 5), np.nanpercentile(ms, 95)
        raw = np.interp(t, tf, (ms - lo) / max(1e-6, hi - lo) * 0.25)
        src_kind = 'lipsync.json dark-gap (normalised to ~0..0.25 IOD)'
    ok = np.isfinite(raw)
    if ok.sum() < 2:
        return
    raw = np.interp(np.arange(n), np.nonzero(ok)[0], raw[ok])
    sh = np.interp(t - lead, t, raw)
    for i, p in enumerate(per):
        p['mouth_open_raw'] = round(float(raw[i]), 4); p['mouth_open'] = round(float(sh[i]), 4)
    per[0]['mouth_track'] = dict(lead_s=lead, source=src_kind)


def clip_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('shot', nargs='?')
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--dur', type=float, default=None)
    ap.add_argument('--layers', default=None)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--src'); ap.add_argument('--out')
    ap.add_argument('--preview-only', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--watch', default=None, help='comma list of shots to wait for in assets/clips/')
    ap.add_argument('--minutes', type=float, default=60); ap.add_argument('--every', type=float, default=4)
    a = ap.parse_args()
    layers = a.layers.split(',') if a.layers else None
    if a.all or a.watch:
        want = set(a.watch.split(',')) if a.watch else None
        t_end = time.time() + a.minutes * 60
        while True:
            for p in sorted(glob.glob(os.path.join(ROOT, 'assets', 'clips', '*.mp4'))):
                s = clip_name(p)
                m = os.path.join(ROOT, 'assets', 'roto', s, 'meta.json')
                fresh = os.path.exists(m) and os.path.getmtime(m) > os.path.getmtime(p) and \
                    all(json.load(open(m))['per_frame'])
                if a.force or not fresh:
                    process(s, layers=layers, workers=a.workers, force=a.force)
            if not a.watch:
                break
            have = {clip_name(p) for p in glob.glob(os.path.join(ROOT, 'assets', 'clips', '*.mp4'))}
            missing = sorted(want - have)
            if not missing or time.time() > t_end:
                print('watch end; missing:', missing, flush=True)
                break
            print(f'waiting for {missing} ...', flush=True)
            time.sleep(a.every * 60)
        return
    if not a.shot:
        ap.error('shot required')
    process(a.shot, a.start, a.dur, layers, a.workers, a.force, a.src, a.out, a.preview_only)


if __name__ == '__main__':
    main()
