# Anime likeness check: the drawn anime Jade layer (flat cel + ink lines, renderer compositing over ink) beside the clip frame.
import cv2, numpy as np, json, os, sys
R = os.path.abspath(os.path.dirname(__file__) + '/../..')
PICKS = [('J6', 40), ('J8', 60), ('J5', 50), ('J1', 60), ('J9', 70), ('J8b', 45)]
rows = []
for j, i in PICKS:
    d = f'{R}/assets/roto/{j}'; meta = json.load(open(d + '/meta.json'))
    cap = cv2.VideoCapture(f"{R}/{meta['src']}"); sf = cap.get(cv2.CAP_PROP_FPS); cap.set(1, round(i / meta['fps'] * sf)); ok, f = cap.read()
    f = cv2.resize(f, (meta['w'], meta['h']))
    cel = cv2.imread(f'{d}/anime/{i:04d}.png', -1); ln = cv2.imread(f'{d}/lines/{i:04d}.png', -1)
    bg = np.full(f.shape, (10, 8, 7), np.uint8); a = cel[..., 3:] / 255.0
    out = (cel[..., :3] * a + bg * (1 - a))
    la = (ln[..., 3:] / 255.0) * a * 0.85; out = out * (1 - la) + np.array([10, 8, 7]) * la
    out = out.astype(np.uint8)
    mt = cel[..., 3] > 0; ys, xs = np.where(mt)
    if ys.size: y0 = max(0, ys.min() - 20); x0 = max(0, int(np.median(xs)) - 380)
    else: y0, x0 = 0, 0
    crop = lambda im: cv2.resize(im[y0:y0 + 760, x0:x0 + 760], (440, 440))
    t1, t2 = crop(f), crop(out)
    cv2.putText(t1, f'{j} clip f{i}', (8, 24), 0, 0.7, (0, 230, 255), 2); cv2.putText(t2, 'drawn (anime cel)', (8, 24), 0, 0.7, (0, 230, 255), 2)
    rows.append(np.hstack([t1, t2]))
grid = np.vstack([np.hstack(rows[k:k + 2]) for k in range(0, len(rows), 2)])
cv2.imwrite(R + '/render/out/anime_check.jpg', grid, [cv2.IMWRITE_JPEG_QUALITY, 90]); print('wrote render/out/anime_check.jpg')
