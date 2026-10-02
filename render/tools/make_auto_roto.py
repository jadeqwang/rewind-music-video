# Interim roto from accepted base clips / set plates (until tools/roto/roto.py delivers assets/roto/<SHOT>/).
# Output: assets/roto/_auto/<name>/ in the renderer's roto format:
#   lines/NNNN.png  DoG line art (white, alpha = line)
#   lights/NNNN.png RGB = the light's own colour, alpha = brightness (streetlights, sirens, headlights) [format addition]
#   matte/NNNN.png  subject mask (GrabCut seeded per frame from the previous one)   [only with --matte rect]
#   meta.json {fps, frames, w, h, layers, src}
# usage: python3 make_auto_roto.py clip  E1 [--matte x0,y0,x1,y1] [--fps 15] [--dur s]
#        python3 make_auto_roto.py plate lake_shore_drive/2 [--matte ...]
import cv2, numpy as np, json, os, sys, subprocess
R = os.path.dirname(os.path.abspath(__file__)) + '/../..'
W, H = 1280, 720

def dog(gray, sigma=1.0, eps=0.3, phi=2.2):
    g = gray.astype(np.float32) / 255
    g1 = cv2.GaussianBlur(g, (0, 0), sigma); g2 = cv2.GaussianBlur(g, (0, 0), sigma * 1.6)
    d = g2 - g1; d = d / max(1e-4, np.percentile(np.abs(d), 98))
    return np.clip((d - eps) * phi, 0, 1)

def clean(l, min_area=40, thr=0.35):
    b = (l > thr).astype(np.uint8); n, lab, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    keep = np.zeros(n, bool); keep[1:] = st[1:, 4] >= min_area; return l * keep[lab]

def save(d, lay, i, rgba):
    os.makedirs(f'{d}/{lay}', exist_ok=True); cv2.imwrite(f'{d}/{lay}/{i:04d}.png', rgba, [cv2.IMWRITE_PNG_COMPRESSION, 3])

def white(a):
    o = np.zeros(a.shape + (4,), np.uint8); o[..., :3] = 255; o[..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8); return o

def process(frames, d, rect=None, src=''):
    os.makedirs(d, exist_ok=True)
    layers = ['lines', 'lights'] + (['matte'] if rect else [])
    prev = None
    for i, im in enumerate(frames):
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
        L = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(lab[..., 0])
        ln = clean(dog(L, eps=0.45), min_area=140 if len(frames) == 1 else 40); ln = cv2.dilate(ln, np.ones((2, 2), np.uint8)) if THICK else ln
        save(d, 'lines', i, white(ln))
        # lights, flattened to the palette: no source pixels survive (hue → sodium / siren red / siren blue / bone)
        v = im.max(2).astype(np.float32) / 255
        a = np.clip((v - 0.72) / 0.25, 0, 1); a = cv2.GaussianBlur(a, (0, 0), 3.0)
        hsv = cv2.cvtColor(cv2.GaussianBlur(im, (0, 0), 3), cv2.COLOR_BGR2HSV); hch, sat = hsv[..., 0].astype(int) * 2, hsv[..., 1] / 255.0
        pal = np.zeros((H, W, 3), np.uint8); pal[:] = (216, 230, 236)                    # bone (BGR)
        pal[(sat > 0.35) & ((hch < 20) | (hch > 330))] = (42, 42, 255)                   # siren red
        pal[(sat > 0.35) & (hch >= 20) & (hch < 60)] = (28, 159, 255)                    # sodium amber
        pal[(sat > 0.35) & (hch >= 190) & (hch < 290)] = (255, 91, 47)                   # siren blue
        li = np.zeros((H, W, 4), np.uint8); li[..., :3] = pal; li[..., 3] = (a * 255).astype(np.uint8)
        save(d, 'lights', i, li)
        if rect:
            # interim matte: dark silhouettes against fog/light (night plates). Pixels darker than a local-contrast
            # threshold inside rect; the dark ground merges in, which reads as figures standing on black.
            x0, y0, x1, y1 = [int(c * s_) for c, s_ in zip(rect, (W, H, W, H))]
            g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 2.0).astype(np.float32)
            bgl = cv2.GaussianBlur(g, (0, 0), 40)
            m = (((g < np.maximum(18, bgl * 0.55)) & (bgl > float(opt.get("--bgmin", 30)))) * 255).astype(np.uint8)
            m[:, :x0] = 0; m[:, x1:] = 0; m[:y0] = 0; m[y1:] = 0
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            n, labs, st, _ = cv2.connectedComponentsWithStats(m)
            mm = np.zeros_like(m)
            for k in range(1, n):
                if st[k, 4] > 2500: mm[labs == k] = 255
            save(d, 'matte', i, white(cv2.GaussianBlur(mm, (0, 0), 0.8).astype(np.float32) / 255))
    meta = dict(fps=FPS, frames=len(frames), w=W, h=H, layers=layers, src=src)
    json.dump(meta, open(d + '/meta.json', 'w')); print(d, len(frames))

args = sys.argv[1:]; kind, name = args[0], args[1]
opt = dict(zip(args[2::2], args[3::2]))
FPS = int(opt.get('--fps', 15)); THICK = opt.get('--thick', '1') == '1'; rect = [float(x) for x in opt['--matte'].split(',')] if '--matte' in opt else None
if kind == 'clip':
    src = f'{R}/assets/clips/{name}.mp4'
    cap = cv2.VideoCapture(src); sfps = cap.get(cv2.CAP_PROP_FPS); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    allf = []
    while True:
        ok, f = cap.read()
        if not ok: break
        allf.append(f)
    dur = len(allf) / sfps; k = int(dur * FPS)
    frames = [allf[min(len(allf) - 1, int(round(i / FPS * sfps)))] for i in range(k)]
    process(frames, f'{R}/assets/roto/_auto/{name}', rect, f'assets/clips/{name}.mp4')
else:
    src = f'{R}/assets/sets/{name}.jpg'
    process([cv2.imread(src)], f'{R}/assets/roto/_auto/plate_{name.replace("/", "_")}', rect, f'assets/sets/{name}.jpg')
