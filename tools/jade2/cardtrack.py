# cardtrack.py: track the blank card she holds (J3 takes) per roto frame → meta.card = [[x,y] x4 (tl, tr, br, bl)] | null
# at roto resolution, so the renderer can warp our drawn generic license onto it. Bright, low-saturation, rectangular blob.
#   python3 tools/jade2/cardtrack.py J3_v3
import os, sys, json, numpy as np, cv2
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')

def order(p):   # tl, tr, br, bl
    p = np.array(p, np.float32); s = p.sum(1); d = np.diff(p, axis=1)[:, 0]
    return [p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]]

# keyframed card boxes (roto frame: x0, y0, x1, y1 at 1920x1080), read off the clip; refined per frame
KEY = {'J3_v3': {15: (566, 650, 696, 732), 20: (608, 590, 740, 672), 30: (677, 503, 830, 597), 40: (807, 492, 972, 605), 52: (927, 530, 1107, 642), 66: (927, 534, 1107, 650), 90: (927, 534, 1112, 647)}}
def interp_box(kb, i):
    ks = sorted(kb)
    if i < ks[0] - 3: return None
    if i <= ks[0]: return kb[ks[0]]
    for a, b in zip(ks, ks[1:]):
        if a <= i <= b: u = (i - a) / (b - a); return tuple(kb[a][q] * (1 - u) + kb[b][q] * u for q in range(4))
    return kb[ks[-1]]
def run(J):
    d = f'{ROOT}/assets/roto/{J}'; meta = json.load(open(d + '/meta.json'))
    cap = cv2.VideoCapture(f"{ROOT}/{meta['src']}"); sfps = cap.get(cv2.CAP_PROP_FPS); frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    W, H = meta['w'], meta['h']; out = []
    for i in range(meta['frames']):
        f = cv2.resize(frames[min(len(frames) - 1, int(round(i / meta['fps'] * sfps)))], (W, H))
        hsv = cv2.cvtColor(cv2.GaussianBlur(f, (5, 5), 0), cv2.COLOR_BGR2HSV); v = hsv[..., 2]
        kb = KEY.get(J); bb = interp_box(kb, i) if kb else None; best = None
        if bb is not None:   # refine inside the keyframed ROI: Otsu on V, the blob under the ROI centre, its min-area rect
            x0, y0, x1, y1 = bb; mx, my = (x1 - x0) * 0.3, (y1 - y0) * 0.45
            X0, Y0, X1, Y1 = int(max(0, x0 - mx)), int(max(0, y0 - my)), int(min(W, x1 + mx)), int(min(H, y1 + my))
            roi = v[Y0:Y1, X0:X1]; _, th = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            n_, l_, st_, cen = cv2.connectedComponentsWithStats(th)
            cx, cy = int((x0 + x1) / 2 - X0), int((y0 + y1) / 2 - Y0); k = l_[min(cy, l_.shape[0] - 1), min(cx, l_.shape[1] - 1)]
            ok = k > 0 and 0.45 < st_[k, 4] / max(1, (x1 - x0) * (y1 - y0)) < 1.6
            if ok:
                cs, _ = cv2.findContours((l_ == k).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                q = cv2.boxPoints(cv2.minAreaRect(max(cs, key=cv2.contourArea))) + np.array([X0, Y0], np.float32)
                kq = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
                best = (1, q) if np.abs(np.sort(q, 0) - np.sort(kq, 0)).max() < 22 else (0, kq)
            else: best = (0, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32))
        out.append([[round(float(x), 1), round(float(y), 1)] for x, y in order(best[1])] if best else None)
    # temporal smoothing (3-tap) + short gap fill
    n = len(out); sm = []
    for i in range(n):
        win = [out[j] for j in range(max(0, i - 1), min(n, i + 2)) if out[j]]
        sm.append([[round(sum(q[k][0] for q in win) / len(win), 1), round(sum(q[k][1] for q in win) / len(win), 1)] for k in range(4)] if win and (out[i] or (i > 0 and i < n - 1 and out[i - 1] and out[i + 1])) else None)
    meta['card'] = sm; json.dump(meta, open(d + '/meta.json', 'w'))
    print(J, sum(1 for p in sm if p), '/', n, 'frames with a card')

if __name__ == '__main__':
    for J in sys.argv[1:]: run(J)
