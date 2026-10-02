# anime_modes.py: A/B sheet for the anime Jade medium → render/out/anime_modes.jpg
# rows = 6 in-scene moments; columns = the clip frame drawn | in-scene with ?jade=cel | in-scene with ?jade=direct
# (the stills log which Jade clip frame they drew: <still>.jade.json)
import os, sys, json, subprocess, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RENDER = os.path.dirname(HERE); ROOT = os.path.dirname(RENDER)
PICKS = [(14.7, 'V1'), (74.8, 'V5'), (148.55, 'D2'), (61.9, 'R6'), (175.9, 'N2'), (102.26, 'F4 freeze')]
if len(sys.argv) > 1: PICKS = [(float(t), f't={t}') for t in sys.argv[1].split(',')]
OUT = f'{RENDER}/out/anime_modes'; CW, CH = 560, 630
def stills(mode):
    d = f'{OUT}/{mode}'; os.makedirs(d, exist_ok=True)
    subprocess.run(['node', 'render.mjs', '--stills', ','.join(str(t) for t, _ in PICKS), '--out', d, '--query', f'jade={mode}'], cwd=RENDER, check=True, stdout=subprocess.DEVNULL)
    return d
def crop(img, cx, cy, h):
    s = CH / h; im = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); x0, y0 = int(cx * s - CW / 2), int(cy * s - CH / 2)
    pad = cv2.copyMakeBorder(im, CH, CH, CW, CW, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return pad[y0 + CH:y0 + 2 * CH, x0 + CW:x0 + 2 * CW]
def label(im, t):
    cv2.rectangle(im, (0, 0), (CW, 34), (0, 0, 0), -1); cv2.putText(im, t, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 230, 255), 2, cv2.LINE_AA); return im
dirs = {m: stills(m) for m in ('cel', 'direct')}
rows = []
for t, name in PICKS:
    stem = f't{t:.3f}'.replace('.', '_'); js = f"{dirs['direct']}/{stem}.jade.json"
    log = json.load(open(js)) if os.path.exists(js) else []
    e = next((x for x in reversed(log) if x.get('rect')), log[-1] if log else None)
    cells = []
    if e:
        d = f"{ROOT}/assets/roto/{e['id']}"; m = json.load(open(d + '/meta.json')); fi = e['fi']
        cap = cv2.VideoCapture(f"{ROOT}/{m['src']}"); sf = cap.get(cv2.CAP_PROP_FPS); cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(fi / m['fps'] * sf))); ok, fr = cap.read()
        fr = cv2.resize(fr, (m['w'], m['h'])) if ok else np.zeros((m['h'], m['w'], 3), np.uint8)
        mt = cv2.imread(f'{d}/matte/{fi:04d}.png', cv2.IMREAD_UNCHANGED); a = mt[..., 3] if mt is not None else np.full(fr.shape[:2], 255, np.uint8)
        ys, xs = np.where(a > 128)
        if ys.size: x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), min(ys.max(), ys.min() + int((xs.max() - xs.min()) * 1.3))
        else: x0, x1, y0, y1 = 0, m['w'], 0, m['h']
        cx, cy, hh = (x0 + x1) / 2, (y0 + y1) / 2, max(200, (y1 - y0) * 1.1)
        cells.append(label(crop(fr, cx, cy, hh), f"{name}  clip {e['id']} f{fi}"))
        r = e['rect']; kx, ky = r['w'] / m['w'], r['h'] / m['h']   # design (1920x1080) = still resolution
        for mode in ('cel', 'direct'):
            st = cv2.imread(f'{dirs[mode]}/{stem}.jpg'); sx = st.shape[1] / 1920
            cells.append(label(crop(st, (r['x'] + cx * kx) * sx, (r['y'] + cy * ky) * sx, hh * ky * sx), f'in-scene · {mode}'))
    else:
        for mode in ('', 'cel', 'direct'): cells.append(label(np.zeros((CH, CW, 3), np.uint8), f'{name} (no jade drawn) {mode}'))
    rows.append(np.hstack(cells))
cv2.imwrite(f'{RENDER}/out/anime_modes.jpg', np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88]); print('wrote render/out/anime_modes.jpg')
