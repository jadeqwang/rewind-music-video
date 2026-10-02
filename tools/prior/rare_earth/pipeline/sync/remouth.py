"""Re-time DOT's mouth to the vocal, keeping her body on the take's own timing (docs/PROCESS.md §3d).

A Seedance take sings the right mouth shapes, but its timing wanders against the song: one lag per shot (§3)
fits one stretch and misses the next ("not that" in sync, "far from my own" not). Warping the whole take would
stall or rush her body. This does what cel animation does instead, and times the mouth separately:

  1. the mouth is tracked through the take (the anime face cascade, image registration of the lower face for the
     extreme close-ups, or boxes placed by hand) and its openness measured in every frame (mouth.openness);
  2. the target is the vocal stem: log RMS x voicing probability, so sung vowels open the mouth, and rests, stops
     and unvoiced consonants close it;
  3. for every drawing the renderer shows in the shot (on twos, at the shot's lag) a mouth is chosen from the same
     take by dynamic programming: openness close to the target, running forward in time like the take does, from
     a frame near the body's own so the head pose is nearly the same, lit like it, and not under a shadow or hand;
  4. that mouth is registered onto the body frame (ECC on the face around the mouth, the mouths masked out) and
     blended in over every mouth pixel of both drawings, taking on the body frame's shading.

The renderer then redraws the plate as ink like any other. Writes <take>_sync.mp4 into pipeline/base_clips/ and a
log of the choices; selects.json points at the result.

  python3 pipeline/sync/remouth.py [sd07 sd10 ...] [--preview DIR]
"""
import json
import os
import subprocess
import sys

import cv2
import librosa
import numpy as np
from scipy.ndimage import gaussian_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mouth  # noqa: E402

CLIPS = os.path.join(HERE, '..', 'base_clips')
VOCALS = '/tmp/work/vocals.wav'      # Kim_Vocal_2 stem (docs/PROCESS.md §1)
FPS = 24

# One entry per take. Shots are the edit's uses of it: (song window, the take's song start, lag) exactly as
# render/src/timeline.js plays them. 'face': how the mouth is found.
#   cascade: the anime face cascade's box (mouth centred at 0.5 w, 0.655 h)
#   track:   a mouth box given at one frame, followed by registering the lower face frame to frame
#   keys:    mouth boxes placed by hand at a few frames, interpolated
PLATES = {
    'sd06': {'src': 'sd06_blink__a30f474b95.mp4', 'face': 'cascade',
             'shots': [('blink', (25.30, 27.82), 25.0, 0.333333)]},
    # extreme close-ups: the head hardly moves, so a mouth can come from further away in the take
    'sd07': {'src': 'sd07_transit__9681e0518b.mp4', 'face': 'track', 'ref': 60, 'box': (652, 478, 92, 64),
             'max_dev': 40, 'w_near': 0.02, 'shots': [('transit_eye', (30.98, 35.94), 30.0, 0.0)]},
    # 'vision' opens on the end of "transmission": its last syllable (-sion) runs to 71.27 on D4, and "Our" starts
    # a tone up. The /ən/ is voiced, so the stem alone would open her mouth for it; it is held nearly shut instead
    'sd10': {'src': 'sd10_vision__1368eb119a.mp4', 'face': 'cascade', 'size': (0.3, 0.24),
             'hold': [(71.10, 71.27, 0.12)],
             'shots': [('vision', (71.14, 72.54), 71.0, 0.0), ('vision2', (73.999, 75.36), 71.0, 0.125)]},
    'sd11': {'src': 'sd11_care__03ce0c9203.mp4', 'face': 'cascade',
             'shots': [('care2', (75.36, 77.66), 75.0, 0.125)]},
    'sd13': {'src': 'sd13_caught_reply__935323d481_lettering.mp4', 'face': 'cascade',
             'shots': [('caught2', (94.61, 97.45), 93.3, -0.333333)]},
    # the push-in turns her from behind into profile, then three-quarter view: the mouth is only drawn from frame 50
    # on, and is placed by hand at a few frames; the back-of-head frames are left alone. In profile the open lips
    # meet the sky, so the mouth can't be told apart by colour: an ellipse around it is transplanted instead
    'sd16': {'src': 'sd16_alone_beam__c43ef1f6ef.mp4', 'face': 'keys', 'frames': (50, 121), 'max_dev': 6,
             'recentre': False, 'mask': (1.9, 2.2), 'clear': None,
             'keys': [(50, 593, 375, 14, 10), (56, 600, 377, 16, 12), (60, 610, 377, 18, 13), (64, 617, 379, 20, 15),
                      (70, 627, 393, 28, 22), (76, 640, 404, 38, 30), (82, 640, 405, 46, 34), (90, 647, 440, 55, 42),
                      (120, 650, 450, 55, 42)],
             'shots': [('alone2', (107.79, 112.02), 107.5, 0.0)]},
    'sd15': {'src': 'sd15_own_ecu__3eb552a647.mp4', 'face': 'track', 'ref': 60, 'box': (638, 500, 130, 80),
             'max_dev': 40, 'w_near': 0.02, 'shots': [('own', (104.34, 107.79), 102.8, -0.083333)]},
}


def read_clip(path):
    cap = cv2.VideoCapture(path)
    out = []
    while True:
        ok, f = cap.read()
        if not ok: break
        out.append(f)
    return out


def write_clip(frames, path):
    h, w = frames[0].shape[:2]
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                          '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                          '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    for f in frames: p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait() != 0: raise RuntimeError('ffmpeg failed: ' + path)


# ------------------------------------------------------------------------------------------------ mouth tracking
def boxes_cascade(frames, size=(0.28, 0.2)):
    fb, _ = mouth.detect_faces(frames)
    # mouth box (cx, cy, w, h): about the size of a half-open mouth, centred at (0.5, 0.655) of the face box
    return np.array([[x + 0.5 * w, y + 0.655 * h, size[0] * w, size[1] * h] for x, y, w, h in fb])


def boxes_tracked(frames, ref, box):
    """Follow the lower face with ECC (affine), frame to frame out from `ref`, the mouth masked out."""
    cx, cy, bw, bh = box
    n = len(frames)
    gray = [cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255, (0, 0), 1.2) for f in frames]
    H, W = gray[0].shape
    x0, y0 = int(max(0, cx - 2.2 * bw)), int(max(0, cy - 2.0 * bh))
    x1, y1 = int(min(W, cx + 2.2 * bw)), int(min(H, cy + 2.2 * bh))
    tmpl_mask = np.zeros((H, W), np.uint8)
    tmpl_mask[y0:y1, x0:x1] = 1
    cv2.ellipse(tmpl_mask, ((cx, cy), (1.3 * bw, 1.6 * bh), 0), 0, -1)
    A = {ref: np.eye(2, 3, dtype=np.float32)}          # maps ref coords -> frame coords
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)
    for step in (1, -1):
        prev = ref
        i = ref + step
        while 0 <= i < n:
            M = A[prev].copy()
            try:
                _, M = cv2.findTransformECC(gray[ref], gray[i], M, cv2.MOTION_AFFINE, crit, tmpl_mask, 5)
            except cv2.error:
                pass
            A[i] = M
            prev = i
            i += step
    out = []
    for i in range(n):
        M = A[i]
        c = M[:, :2] @ np.array([cx, cy]) + M[:, 2]
        s = np.sqrt(abs(np.linalg.det(M[:, :2])))
        out.append([c[0], c[1], bw * s, bh * s])
    return np.array(out)


def recentre(frames, boxes):
    """Centre each frame's mouth box on the mouth actually drawn there (tracking drifts on flat skin); the box keeps
    its size. Smoothed over time, and left alone where no mouth is found."""
    c = []
    for f, (cx, cy, w, h) in zip(frames, boxes):
        m = mouth_pixels(f, cx, cy, w, h)
        pts = cv2.findNonZero(m)
        if pts is None or len(pts) < 10:
            c.append([np.nan, np.nan]); continue
        x, y, bw_, bh_ = cv2.boundingRect(pts)
        c.append([x + bw_ / 2, y + bh_ / 2])
    c = np.array(c)
    out = boxes.copy()
    for k in range(2):
        ok = np.isfinite(c[:, k])
        if ok.sum() < 3: continue
        v = np.interp(np.arange(len(c)), np.flatnonzero(ok), c[ok, k])
        out[:, k] = gaussian_filter1d(v, 1.0)
    return out


def lighting(frames, boxes):
    """Median luminance of the skin around each frame's mouth (a beam or a hand's shadow changes it), and how much
    of that surround is clear skin: a shadow or a hand over it makes a frame a poor source of mouths."""
    lum, clear = [], []
    for f, (cx, cy, w, h) in zip(frames, boxes):
        ring = (ellipse_mask(f.shape, cx, cy, 3.2 * w, 3.2 * h) & (1 - ellipse_mask(f.shape, cx, cy, 1.6 * w, 1.8 * h))) > 0
        sk = skin(f)
        px = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[ring & sk]
        lum.append(float(np.median(px)) if len(px) > 20 else np.nan)
        clear.append(float((ring & sk).sum()) / max(1, ring.sum()))
    v = np.array(lum)
    ok = np.isfinite(v)
    v = np.interp(np.arange(len(v)), np.flatnonzero(ok), v[ok]) if ok.any() else np.zeros(len(v))
    return v, np.array(clear)


def openness(frames, boxes):
    op = []
    for f, (cx, cy, w, h) in zip(frames, boxes):
        o, _ = mouth.openness(f, (int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)))
        op.append(o)
    op = np.array(op)
    lo, hi = np.percentile(op, 5), np.percentile(op, 95)
    return np.clip((op - lo) / (hi - lo + 1e-9), 0, 1.2)


# ------------------------------------------------------------------------------------------------ the vocal
_VOC = None


def vocal_target():
    """Log RMS and voicing probability of the vocal stem at 100 Hz."""
    global _VOC
    if _VOC is None:
        y, sr = librosa.load(VOCALS, sr=16000, mono=True)
        hop = 160
        rms = librosa.feature.rms(y=y, frame_length=640, hop_length=hop, center=True)[0]
        _, _, vp = librosa.pyin(y, fmin=150, fmax=1000, sr=sr, frame_length=1024, hop_length=hop)
        n = min(len(rms), len(vp))
        _VOC = (np.arange(n) * hop / sr, gaussian_filter1d(np.log(rms[:n] + 1e-5), 2.0),
                gaussian_filter1d(np.nan_to_num(vp[:n]), 2.0))
    return _VOC


def target_at(ts, win):
    """0 = closed, 1 = open. Loudness is compressed (log RMS), so a low, quiet vowel still opens the mouth, and
    weighted by the voicing probability, so silences, stops and unvoiced consonants (s, f, th, t) close it."""
    t, lr, vp = vocal_target()
    m = (t >= win[0] - 1) & (t <= win[1] + 1)
    lo, hi = np.percentile(lr[m], 10), np.percentile(lr[m], 90)
    v = np.clip((lr - lo) / (hi - lo + 1e-9), 0, 1.1) * np.clip(vp / 0.6, 0, 1) ** 0.7
    return np.interp(ts, t, v)


# ------------------------------------------------------------------------------------------------ choosing mouths
def display_units(win, start, lag, n):
    """The even frames the renderer shows in the window (drawings on twos), with the song time at their middle."""
    ts = np.arange(win[0], win[1], 1 / 240)
    f = np.floor((ts - start + lag) * FPS + 1e-3).astype(int)
    f = np.clip(f - f % 2, 0, n - 1)
    units = []
    for e in np.unique(f):
        tt = ts[f == e]
        units.append((int(e), float(tt.mean())))
    return units


def choose(units, op, target, light=None, max_dev=18, w_near=0.25, w_cont=0.05, w_light=0.6):
    n = len(op)
    K = len(units)
    J = np.arange(n)
    INF = 1e9
    cost = np.full((K, n), INF)
    back = np.zeros((K, n), int)
    for k, (e, t) in enumerate(units):
        u = (op - target[k]) ** 2 + w_near * ((J - e) / 12.0) ** 2
        if light is not None: u = u + w_light * ((light - light[e]) / 12.0) ** 2
        u[np.abs(J - e) > max_dev] = INF
        if k == 0:
            cost[0] = u
            continue
        # pairwise: a mouth advances like the take (2 frames per drawing); holds and small skips cost a little
        d = J[None, :] - J[:, None] - 2
        pair = w_cont * np.minimum((d / 2.0) ** 2, 9.0) + 0.02 * (d < -2)      # going backwards costs a bit more
        tot = cost[k - 1][:, None] + pair
        back[k] = np.argmin(tot, 0)
        cost[k] = tot[back[k], J] + u
    path = [int(np.argmin(cost[-1]))]
    for k in range(K - 1, 0, -1): path.append(int(back[k][path[-1]]))
    return path[::-1]


# ------------------------------------------------------------------------------------------------ compositing
def ellipse_mask(shape, cx, cy, w, h):
    m = np.zeros(shape[:2], np.uint8)
    cv2.ellipse(m, ((float(cx), float(cy)), (float(w), float(h)), 0), 1, -1)
    return m


def skin(img):
    """DOT's skin (the test mouth.openness uses): everything else near the mouth is mouth, lips or teeth."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    return ((h < 40) | (h > 340)) & (s > 0.07) & (s < 0.42) & (v > 0.62)


def mouth_pixels(img, cx, cy, bw, bh):
    """The drawn mouth near (cx, cy): non-skin shapes that reach into the mouth box (so the nose, the chin line and
    hair are left out), with their holes filled (a pink tongue can pass the skin test)."""
    search = ellipse_mask(img.shape, cx, cy + 0.1 * bh, 2.8 * bw, 3.2 * bh)
    m = ((~skin(img)) & (search > 0)).astype(np.uint8)
    # no opening here: it would erase the thin ends of a closed mouth's line, and leave them behind. A flat closing
    # bridges the breaks where a tapering line is anti-aliased light enough to pass for skin.
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 31), np.uint8))
    core = ellipse_mask(img.shape, cx, cy + 0.1 * bh, 1.0 * bw, 1.3 * bh)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    hit = np.unique(lab[(core > 0) & (m > 0)])
    # a shape much bigger than a mouth is the chin, the neck or hair reaching into the box, not the mouth
    hit = [k for k in hit if k > 0 and 8 <= st[k, cv2.CC_STAT_AREA] <= 2.0 * bw * bh]
    keep = np.isin(lab, hit).astype(np.uint8)
    cnts, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(keep)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return filled


def register(body, src, bbox, sbox, use_pixels=True):
    """Affine map src -> body from the face around the mouth (ECC; the mouths themselves masked out)."""
    H, W = body.shape[:2]
    cx, cy, bw, bh = bbox
    gb = cv2.GaussianBlur(cv2.cvtColor(body, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255, (0, 0), 1.5)
    gs = cv2.GaussianBlur(cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255, (0, 0), 1.5)
    mask = np.zeros((H, W), np.uint8)
    x0, y0 = int(max(0, cx - 2.4 * bw)), int(max(0, cy - 2.6 * bh))
    x1, y1 = int(min(W, cx + 2.4 * bw)), int(min(H, cy + 2.6 * bh))
    mask[y0:y1, x0:x1] = 1
    if use_pixels: mask[mouth_pixels(body, cx, cy, bw, bh) > 0] = 0
    else: mask[ellipse_mask(body.shape, cx, cy, 1.9 * bw, 2.2 * bh) > 0] = 0
    mask = cv2.erode(mask, np.ones((9, 9), np.uint8))
    s = bw / max(1e-6, sbox[2])
    M = np.array([[s, 0, cx - s * sbox[0]], [0, s, cy - s * sbox[1]]], np.float32)
    try:
        # ECC solves body(x) ~ src(W x), i.e. W maps body coordinates to src coordinates
        Winv = cv2.invertAffineTransform(M).astype(np.float32)
        _, Winv = cv2.findTransformECC(gb, gs, Winv, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6), mask, 5)
        M2 = cv2.invertAffineTransform(Winv)
        # distrust a registration that wanders far from the boxes' guess
        if np.abs(M2[:, 2] + M2[:, :2] @ np.array(sbox[:2]) - np.array([cx, cy])).max() < 0.5 * bh: M = M2
    except cv2.error:
        pass
    return M


def composite(body, src, bbox, sbox, ellipse=None):
    """Register src's face onto body's around the mouth; replace body's mouth with src's. ellipse=(sx, sy): take a
    fixed ellipse around both mouths instead of the mouth pixels (for profiles, where the lips meet the sky)."""
    H, W = body.shape[:2]
    cx, cy, bw, bh = bbox
    M = register(body, src, bbox, sbox, use_pixels=ellipse is None)
    warped = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if ellipse is not None:
        sc = M[:, :2] @ np.array(sbox[:2]) + M[:, 2]
        k = np.sqrt(abs(np.linalg.det(M[:, :2])))
        m = ellipse_mask(body.shape, cx, cy, ellipse[0] * bw, ellipse[1] * bh) | \
            ellipse_mask(body.shape, sc[0], sc[1], ellipse[0] * sbox[2] * k, ellipse[1] * sbox[3] * k)
        a = cv2.GaussianBlur(m.astype(np.float32), (0, 0), max(1.2, 0.12 * bh))
        out = body.astype(np.float32) * (1 - a[..., None]) + warped.astype(np.float32) * a[..., None]
        composite.remnant = 0
        return np.clip(out, 0, 255).astype(np.uint8)
    # everything that is mouth in either picture, with a margin of skin for the feather to live in
    m = mouth_pixels(body, cx, cy, bw, bh) | mouth_pixels(warped, cx, cy, bw, bh)
    pts = cv2.findNonZero(m)
    if pts is not None:
        cv2.fillConvexPoly(m, cv2.convexHull(pts), 1)
    # down over the lower lip's shading, which belongs to the drawing of the mouth above it
    down = max(3, int(round(0.35 * bh)))
    m = cv2.dilate(m, np.ones((down, 1), np.uint8), anchor=(0, down - 1))
    grow = int(round(0.10 * bh)) * 2 + 3
    # wider than tall: a mouth's corners taper to thin lines that a round margin would barely cover
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(grow * 1.8) | 1, grow))).astype(np.float32)
    a = cv2.GaussianBlur(m, (0, 0), max(1.2, 0.035 * bh))
    # carry the body's shading (a beam, a shadow) onto the transplant: the ratio of the two pictures' skin, blurred
    # to low frequencies with the mouths left out (normalised convolution), multiplies the transplanted pixels
    wt = (skin(body) & skin(warped) & (m == 0)).astype(np.float32)
    sig = max(3.0, 0.6 * bh)
    den = cv2.GaussianBlur(wt, (0, 0), sig) + 1e-3
    wf = warped.astype(np.float32)
    lb = cv2.GaussianBlur(body.astype(np.float32) * wt[..., None], (0, 0), sig) / den[..., None]
    lw = cv2.GaussianBlur(wf * wt[..., None], (0, 0), sig) / den[..., None]
    ratio = np.where(den[..., None] > 0.05, (lb + 1) / (lw + 1), 1.0)
    wf = np.clip(wf * np.clip(ratio, 0.6, 1.6), 0, 255)
    out = np.clip(body.astype(np.float32) * (1 - a[..., None]) + wf * a[..., None], 0, 255).astype(np.uint8)
    # QA: mouth left in the result that is not the transplanted mouth (a remnant of the body's own)
    got = mouth_pixels(out, cx, cy, bw, bh)
    want = cv2.dilate(mouth_pixels(warped, cx, cy, bw, bh), np.ones((5, 5), np.uint8))
    composite.remnant = int(((got > 0) & (want == 0)).sum())
    return out


def run(key, preview=None):
    spec = PLATES[key]
    frames = read_clip(os.path.join(CLIPS, spec['src']))
    n = len(frames)
    if spec['face'] == 'cascade':
        boxes = boxes_cascade(frames, spec.get('size', (0.28, 0.2)))
    elif spec['face'] == 'keys':
        k = np.array(spec['keys'], float)
        boxes = np.stack([np.interp(np.arange(n), k[:, 0], k[:, c]) for c in range(1, 5)], 1)
    else:
        boxes = boxes_tracked(frames, spec['ref'], spec['box'])
    lo, hi = spec.get('frames', (0, n))
    if spec.get('recentre', True): boxes = recentre(frames, boxes)
    op = openness(frames, boxes)
    light, clear = lighting(frames, boxes)
    out = list(frames)
    log = {'openness': [round(float(v), 3) for v in op], 'clear': [round(float(v), 3) for v in clear], 'shots': {}}
    for name, win, start, lag in spec['shots']:
        units = [u for u in display_units(win, start, lag, n) if lo <= u[0] < hi]
        tgt = target_at(np.array([t for _, t in units]), win)
        for a, b, v in spec.get('hold', []):            # phonemes the stem can't tell apart (a voiced /n/)
            tgt[[a <= t < b for _, t in units]] = v
        opr = op.copy()
        opr[:lo] = 99; opr[hi:] = 99                  # mouths come from the same frame range
        if spec.get('clear', 0.8):                    # and not from under a shadow or a hand
            opr[clear < spec.get('clear', 0.8) * np.median(clear[lo:hi])] = 99
        path = choose(units, opr, tgt, light, max_dev=spec.get('max_dev', 18), w_near=spec.get('w_near', 0.25))
        rem = []
        for (e, t), j in zip(units, path):
            composite.remnant = 0
            new = frames[e] if j == e else composite(frames[e], frames[j], boxes[e], boxes[j], spec.get('mask'))
            rem.append(composite.remnant)
            out[e] = new
            if e + 1 < n: out[e + 1] = new        # odd frames are not shown on twos; keep them consistent anyway
        log['shots'][name] = [{'body': e, 'mouth': j, 't': round(t, 3), 'target': round(float(g), 3), 'open': round(float(op[j]), 3),
                               'remnant': r} for (e, t), j, g, r in zip(units, path, tgt, rem)]
        print(f'  {name}: {len(units)} drawings, {sum(j != e for (e, _), j in zip(units, path))} re-mouthed, '
              f'worst remnant {max(rem)} px', flush=True)
    dst = os.path.join(CLIPS, spec['src'].replace('.mp4', '_sync.mp4'))
    write_clip(out, dst)
    if preview:
        os.makedirs(preview, exist_ok=True)
        json.dump({'boxes': boxes.tolist(), **log}, open(f'{preview}/{key}_remouth.json', 'w'))
        for i in range(0, n, 2): cv2.imwrite(f'{preview}/{key}_{i:04d}.jpg', out[i])
    return dst


if __name__ == '__main__':
    keys = [a for a in sys.argv[1:] if a in PLATES] or list(PLATES)
    prev = sys.argv[sys.argv.index('--preview') + 1] if '--preview' in sys.argv else None
    for k in keys: print(k, '->', run(k, prev), flush=True)
