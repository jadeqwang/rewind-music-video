#!/usr/bin/env python3
"""v2 first frames: crop the 1536x1024 jacket edit to 16:9 (rows 80..944, as jacket_v2.py padded it), then paste the v1 frame's
FACE back pixel-exact (template match +-30 px, scale 0.95-1.05, feathered ellipse inside the face box, chin/neck excluded so the
new collar survives).  Usage: shotpaste.py SHOT CAND OUT.jpg [neck_frac=0.92]   (writes OUT and OUT_720)"""
import sys, numpy as np, cv2
sys.path.insert(0, "/home/user/rewind-music-video/tools/anime")
import framemeasure as FM
A = "/home/user/rewind-music-video/assets/character/anime/shots"
MANUAL = {"J8b": (735, 205, 905, 355)}   # 3/4-back face MediaPipe misses (x0 y0 x1 y1)
def run(shot, cand, out, nf=0.92):
    V1 = cv2.imread(f"{A}/{shot}.jpg"); E = cv2.resize(cv2.imread(cand), (1536, 1024))[80:944]
    box = MANUAL.get(shot) or FM.find_face(cv2.cvtColor(V1, cv2.COLOR_BGR2RGB))
    if box is None: print(shot, "no face: crop only"); R = E
    else:
        x0, y0, x1, y1 = [int(v) for v in box]; w, h = x1 - x0, y1 - y0
        X0, Y0, X1, Y1 = max(0, x0 - w // 6), max(0, y0 - h // 3), min(1536, x1 + w // 6), min(864, y0 + int(nf * h))
        T = V1[Y0:Y1, X0:X1].astype(np.float32); Ef = E.astype(np.float32); best = (-1, None); m = 30
        for s in np.linspace(0.95, 1.05, 11):
            Ts = cv2.resize(T, None, fx=s, fy=s); sx, sy = max(0, X0 - m), max(0, Y0 - m)
            S = Ef[sy:min(864, Y1 + m + 10), sx:min(1536, X1 + m + 10)]
            if S.shape[0] < Ts.shape[0] or S.shape[1] < Ts.shape[1]: continue
            r = cv2.matchTemplate(S, Ts, cv2.TM_CCOEFF_NORMED); _, v, _, loc = cv2.minMaxLoc(r)
            if v > best[0]: best = (v, (s, sx + loc[0], sy + loc[1], Ts))
        v, (s, px, py, Ts) = best; hh, ww = Ts.shape[:2]
        mask = np.zeros((hh, ww), np.float32)
        cv2.ellipse(mask, (ww // 2, int(hh * 0.5)), (int(ww * 0.42), int(hh * 0.47)), 0, 0, 360, 1, -1)
        mask = cv2.GaussianBlur(mask, (0, 0), max(3, 0.05 * ww))[..., None]
        R = Ef.copy(); R[py:py + hh, px:px + ww] = Ts * mask + R[py:py + hh, px:px + ww] * (1 - mask)
        print(f"{shot}: corr {v:.3f} scale {s:.2f} dx {px - X0} dy {py - Y0} box {w}x{h}")
    R = np.clip(R, 0, 255).astype(np.uint8)
    cv2.imwrite(out, R, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(out.replace(".jpg", "_720.jpg"), cv2.resize(R, (1280, 720), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 95])
if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.92)
