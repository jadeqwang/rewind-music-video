# ANIME Jade layer: flat cel regions quantized to her canonical anime palette (assets/character/anime/CANON_SHEET.jpg),
# from anime Seedance footage + its roto (matte/face/hair/lines). Never shows source pixels: every region is a flat
# palette colour with spline-smoothed boundaries; the footage's own anime eyes/brows/mouth come through as flat ink / eye
# colour shapes. Roto linework is added in ink by the renderer (roto.jade2 draws 'lines' over the cel).
#   python3 tools/jade2/anime.py J3 [J5 ...] [--frames a:b]      → assets/roto/<J>/anime/NNNN.png + anime.json
#   python3 tools/jade2/anime.py --still IMG OUT.png              → test on a still (isnet matte)
import os, sys, json, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import chaikin, smooth_fill
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')
# canonical palette (BGR)
P = dict(skin=(203, 220, 242), skin_sh=(168, 186, 222), hair=(22, 18, 20), hair_sheen=(70, 62, 66), jacket=(232, 234, 234),
         jacket_sh=(176, 180, 186), orange=(48, 130, 236), patch=(232, 176, 128), black=(14, 12, 13), eye=(40, 46, 62),
         eye_white=(240, 242, 244), mouth=(120, 124, 196), shoe=(236, 236, 236))

def isnet_matte(bgr):
    import onnxruntime as ort
    s = ort.InferenceSession(ROOT + '/tools/roto/models/isnet-general-use.onnx', providers=['CPUExecutionProvider'])
    x = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), (1024, 1024)).astype(np.float32) / 255.0
    x = (x - 0.5) / 1.0; x = x.transpose(2, 0, 1)[None]
    y = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    y = (y - y.min()) / max(1e-6, y.max() - y.min())
    return cv2.resize(y, (bgr.shape[1], bgr.shape[0]))

def classify(bgr, matte, face=None, hair=None):
    H, W = matte.shape
    sm = bgr.copy()
    for _ in range(3): sm = cv2.bilateralFilter(sm, 9, 30, 7)
    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV); h, s, v = hsv[..., 0].astype(int) * 2, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    fig = matte > 0.5
    # brightness normalised against the figure (night footage is dim / tinted)
    vf = v[fig]; v_lo, v_hi = (np.percentile(vf, 8), np.percentile(vf, 97)) if vf.size else (0, 1)
    vn = np.clip((v - v_lo) / max(1e-3, v_hi - v_lo), 0, 1)
    lab = np.zeros((H, W), np.uint8)   # 0 = none
    names = list(P.keys()); idx = {k: i + 1 for i, k in enumerate(names)}
    warm = ((h < 40) | (h > 340)) & (s > 0.12) & (s < 0.55)
    orange = (h >= 10) & (h <= 40) & (s > 0.45) & (vn > 0.3)
    blue = (h >= 190) & (h <= 240) & (s > 0.25) & (vn > 0.35)
    dark = (v < 0.2) | (vn < 0.12)
    skinlike = warm & (v > 0.35)
    if face is None or face.sum() < 0.002 * H * W:   # no usable face mask (MediaPipe misses anime faces): largest warm-skin blob in the upper figure
        ys = np.where(fig.any(1))[0]; top = ys.min() if ys.size else 0; cut = top + (ys.max() - top) * 0.45 if ys.size else H
        sk = (skinlike & fig).astype(np.uint8); sk[int(cut):] = 0
        sk = cv2.morphologyEx(sk, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
        n, l, st, _ = cv2.connectedComponentsWithStats(sk)
        face = np.zeros((H, W), bool)
        if n > 1:
            k = 1 + int(np.argmax(st[1:, 4])); face = l == k
            cs, _ = cv2.findContours(face.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            face = np.zeros((H, W), np.uint8); cv2.drawContours(face, cs, -1, 1, -1); face = face > 0
    if hair is None: hair = np.zeros((H, W), bool)
    face = face & fig; hair = hair & fig & ~cv2.erode(face.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    # outfit / body
    lab[fig] = idx['jacket']
    lab[fig & (vn < 0.62)] = idx['jacket_sh']
    lab[fig & dark] = idx['black']
    hands = (fig & skinlike & ~dark & ~face).astype(np.uint8)   # hands only: small warm blobs (warm-lit jacket stays jacket)
    n_, l_, st_, _ = cv2.connectedComponentsWithStats(hands); keep = np.zeros(n_, bool); keep[1:] = st_[1:, 4] < 0.012 * H * W
    lab[keep[l_] & (hands > 0)] = idx['skin']
    lab[fig & orange & ~face] = idx['orange']
    lab[fig & blue & ~face] = idx['patch']
    lab[hair & dark] = idx['hair']; lab[hair & ~dark & (vn < 0.45)] = idx['hair_sheen']
    # face: skin + one shadow tone; eyes/brows dark → eye ink; very bright small → eye white; reddish → mouth
    if face.any():
        fv = vn[face]; t_sh = np.percentile(fv, 22)
        lab[face] = idx['skin']; lab[face & (vn < t_sh) & ~dark] = idx['skin_sh']
        inner = cv2.erode(face.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
        lab[face & dark & ~inner] = idx['hair']
        lab[inner & ((v < 0.36) | dark)] = idx['eye']   # irises / lash lines / brows (face-relative darks)
        lab[face & (vn > 0.92) & (s < 0.12)] = idx['eye_white']
        lab[face & (h < 20) & (s > 0.35) & (vn > 0.35) & (vn < 0.85)] = idx['mouth']
    return lab, names

def render(lab, names, matte):
    H, W = lab.shape; out = np.zeros((H, W, 4), np.uint8)
    fig = (cv2.GaussianBlur(matte, (0, 0), 2) > 0.5).astype(np.uint8)
    fig = cv2.morphologyEx(fig, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    smooth_fill(fig, (*P['jacket'], 255), out, min_area=3000, step=6, it=3)
    order = ['jacket_sh', 'skin', 'skin_sh', 'orange', 'patch', 'black', 'hair', 'hair_sheen', 'mouth', 'eye_white', 'eye']
    for k in order:
        m = (lab == names.index(k) + 1).astype(np.uint8) & fig
        small = k in ('eye', 'eye_white', 'mouth')
        if not small: m = cv2.morphologyEx(cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        if small:   # features: keep compact blobs only (never fill rings)
            n, l, st, _ = cv2.connectedComponentsWithStats(m); m2 = np.zeros_like(m)
            for j in range(1, n):
                if 30 < st[j, 4] < 0.004 * H * W: m2[l == j] = 1
            m = m2
        lay = np.zeros((H, W, 4), np.uint8)   # own layer: holes punch only this label, never what is under it
        smooth_fill(m, (*P[k], 255), lay, min_area=30 if small else 900, step=2 if small else 5, it=2 if small else 3, holes=True)
        al = lay[..., 3:4] / 255.0; out[..., :3] = (lay[..., :3] * al + out[..., :3] * (1 - al)).astype(np.uint8)
    return out

def eye_size(lab, names, face):
    """mean eye-ink blob height / face height (for the >5% shrink clamp vs canon)"""
    m = ((lab == names.index('eye') + 1) & face).astype(np.uint8)
    n, l, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 3: return None
    blobs = sorted(st[1:], key=lambda r: -r[4])[:2]
    ys, xs = np.where(face); fh = ys.max() - ys.min() if ys.size else 1
    return float(np.mean([b[3] for b in blobs]) / max(1, fh))

def grow_eyes(lab, names, face, k):
    ie, iw = names.index('eye') + 1, names.index('eye_white') + 1
    m = (((lab == ie) | (lab == iw)) & face).astype(np.uint8)
    n, l, st, cen = cv2.connectedComponentsWithStats(m)
    out = lab.copy()
    for j in sorted(range(1, n), key=lambda j: -st[j, 4])[:2]:
        x, y, w, h, _ = st[j]; cx, cy = cen[j]
        M = np.float32([[k, 0, cx * (1 - k)], [0, k, cy * (1 - k)]])
        patch = np.where(l == j, lab, 0).astype(np.uint8)
        big = cv2.warpAffine(patch, M, (lab.shape[1], lab.shape[0]), flags=cv2.INTER_NEAREST)
        out[big > 0] = big[big > 0]
    return out

def run_clip(J, fr=None):
    d = f'{ROOT}/assets/roto/{J}'; meta = json.load(open(d + '/meta.json'))
    cap = cv2.VideoCapture(f"{ROOT}/{meta['src']}"); sfps = cap.get(cv2.CAP_PROP_FPS); frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    a = lambda p: (cv2.imread(p, cv2.IMREAD_UNCHANGED)[..., 3] / 255.0) if os.path.exists(p) else None
    os.makedirs(d + '/anime', exist_ok=True); info = {}; cache = {}; names = list(P.keys())
    for i in (range(meta['frames']) if fr is None else range(*fr)):
        f = cv2.resize(frames[min(len(frames) - 1, int(round(i / meta['fps'] * sfps)))], (meta['w'], meta['h']), interpolation=cv2.INTER_CUBIC)
        mt = a(f'{d}/matte/{i:04d}.png'); fc = a(f'{d}/face/{i:04d}.png'); hr = a(f'{d}/hair/{i:04d}.png')
        face = (fc > 0.5) if fc is not None else None; hair = (hr > 0.5) if hr is not None else None
        lab, names = classify(f, mt, face, hair)
        cache[i] = (lab, mt.astype(np.float16), face)
        info[i] = dict(eye=eye_size(lab, names, face) if face is not None else None)
    # eye clamp: canon eye size = the clip's 90th percentile (gen footage only ever shrinks them); frames > 5 % smaller
    # get their eye shapes scaled back up about each eye's centroid before rendering
    es = [v['eye'] for v in info.values() if v['eye']]; ref = float(np.percentile(es, 90)) if es else None
    for i, v in info.items():
        # only where measurable: plausible eye blob (4–20 % of face height); never more than +8 % (anime eyes are canon-sized)
        ok = ref and 0.04 < ref < 0.2 and v['eye'] and 0.5 * ref < v['eye'] < ref * 0.95
        v['eye_scale'] = min(1.08, ref / v['eye']) if ok else 1.0
        lab, mt, face = cache[i]
        mt = mt.astype(np.float32)
        if v['eye_scale'] > 1.0 and face is not None: lab = grow_eyes(lab, names, face, v['eye_scale'])
        cv2.imwrite(f'{d}/anime/{i:04d}.png', render(lab, names, mt))
    json.dump(dict(eye_ref=ref, frames={str(k): v for k, v in info.items()}), open(d + '/anime.json', 'w'))
    if 'anime' not in meta['layers']: meta['layers'].append('anime'); json.dump(meta, open(d + '/meta.json', 'w'))
    print(J, len(info), 'eye_ref', ref)

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--still':
        img = cv2.imread(a[1]); mt = isnet_matte(img)
        lab, names = classify(img, mt)
        out = render(lab, names, mt); cv2.imwrite(a[2], out); print('wrote', a[2])
    else:
        fr = None
        if '--frames' in a: k = a.index('--frames'); fr = tuple(map(int, a[k + 1].split(':'))); a = a[:k] + a[k + 2:]
        for J in a: run_clip(J, fr)
