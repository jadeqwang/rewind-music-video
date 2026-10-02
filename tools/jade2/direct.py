# ANIME-DIRECT Jade layer: she is the one element rendered in her own medium (the anime footage itself), because she
# is the time-immune one. Mattes her out of the clip with the roto matte (1 px choke + soft edge) and grades the
# footage pixels into the REDACTED NOCTURNE palette: blacks deepened to ink, whites lifted toward bone, a slight
# saturation trim, and a subtle cel-snap of the shading. Scene light, the ink outline, roto line boil, the rewind
# shimmer and grain are added by the renderer (roto.jade2, ?jade=direct).
#   python3 tools/jade2/direct.py J1 [J5 ...]   → assets/roto/<J>/direct/NNNN.webp (RGBA) and adds 'direct' to meta.layers
import os, sys, json, numpy as np, cv2
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')
INK = np.array([10, 8, 7], np.float32) / 255     # BGR of PAL.ink #07080A, lifted a hair so the outline still reads
BONE = np.array([216, 230, 236], np.float32) / 255  # BGR of PAL.bone #ECE6D8

def grade(bgr, snap=0.28, sat=0.9):
    x = bgr.astype(np.float32) / 255
    # levels: crush the lowest 5 % to ink, roll the top into bone (channel-wise, so whites take bone's warmth)
    x = np.clip((x - 0.05) / 0.9, 0, 1)
    x = x * x * (3 - 2 * x) * 0.35 + x * 0.65                # a gentle S for anime contrast
    L = x @ np.array([0.114, 0.587, 0.299], np.float32)
    # cel-snap: pull luminance part-way toward 6 flat bands (edge-preserving: bands are taken on a bilateral copy)
    Ls = cv2.bilateralFilter(L, 7, 0.08, 5)
    Lq = np.round(Ls * 6) / 6
    Lt = L + (Lq - Ls) * snap
    x = x * (np.clip(Lt, 0, 1) / np.maximum(L, 1e-3))[..., None]
    L2 = x @ np.array([0.114, 0.587, 0.299], np.float32)
    x = L2[..., None] + (x - L2[..., None]) * sat             # trim saturation into the palette (orange stays orange)
    x = np.clip(x, 0, 1)
    x = INK + (BONE - INK) * x                                # map 0..1 onto ink..bone
    return np.clip(x * 255, 0, 255).astype(np.uint8)

def alpha(mt):
    a = (mt > 0.5).astype(np.uint8)
    a = cv2.morphologyEx(a, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    a = cv2.erode(a, np.ones((3, 3), np.uint8))               # 1 px choke: no halo of the clip background
    soft = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 1.1)
    return np.clip(soft, 0, 1)

def run_clip(J, full=False):
    d = f'{ROOT}/assets/roto/{J}'; meta = json.load(open(d + '/meta.json'))
    cap = cv2.VideoCapture(f"{ROOT}/{meta['src']}"); sfps = cap.get(cv2.CAP_PROP_FPS); frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    os.makedirs(d + '/direct', exist_ok=True)
    rd = lambda p: (cv2.imread(p, cv2.IMREAD_UNCHANGED)[..., 3] / 255.0).astype(np.float32) if os.path.exists(p) else None
    for i in range(meta['frames']):
        f = cv2.resize(frames[min(len(frames) - 1, int(round(i / meta['fps'] * sfps)))], (meta['w'], meta['h']), interpolation=cv2.INTER_AREA)
        mt = rd(f'{d}/matte/{i:04d}.png')
        a = np.ones(f.shape[:2], np.float32) if (full or mt is None or mt.mean() < 0.01) else alpha(mt)   # ECU (Jeyes): the frame is her
        out = np.dstack([grade(f), (a * 255).astype(np.uint8)])
        out[a < 0.004] = 0
        cv2.imwrite(f'{d}/direct/{i:04d}.webp', out, [cv2.IMWRITE_WEBP_QUALITY, 90])
    if 'direct' not in meta['layers']: meta['layers'].append('direct'); json.dump(meta, open(d + '/meta.json', 'w'))
    print(J, meta['frames'], 'direct')

if __name__ == '__main__':
    a = sys.argv[1:]; full = '--full' in a; a = [x for x in a if x != '--full']
    for J in a: run_clip(J, full)
