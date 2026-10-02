"""Paste the ORIGINAL anime faces (refs/jade/Pasted image.png, padded to 1536x1024) pixel-exact back onto an edited
sheet, aligned per head by template matching (+-40 px, scale 0.94-1.06), feathered mask. Usage: facepaste.py EDIT OUT"""
import sys, numpy as np, cv2
ROOT = "/home/user/rewind-music-video"
BOXES = [(150, 40, 255, 166), (515, 45, 620, 166), (888, 45, 966, 160)]   # face regions in orig_padded coords (above headphones)
def paste(edit_path, out_path, orig_path=ROOT + "/assets/character/anime/cands/orig_padded.jpg"):
    O = cv2.imread(orig_path).astype(np.float32); E = cv2.imread(edit_path).astype(np.float32); R = E.copy()
    for (x0, y0, x1, y1) in BOXES:
        T = O[y0:y1, x0:x1]; best = (-1, None)
        for s in np.linspace(0.94, 1.06, 13):
            Ts = cv2.resize(T, None, fx=s, fy=s); m = 40
            sx0, sy0 = max(0, x0 - m), max(0, y0 - m); S = E[sy0:y1 + m + 10, sx0:x1 + m + 10]
            if S.shape[0] < Ts.shape[0] or S.shape[1] < Ts.shape[1]: continue
            r = cv2.matchTemplate(S, Ts, cv2.TM_CCOEFF_NORMED); _, v, _, loc = cv2.minMaxLoc(r)
            if v > best[0]: best = (v, (s, sx0 + loc[0], sy0 + loc[1], Ts))
        v, (s, px, py, Ts) = best; h, w = Ts.shape[:2]
        mask = np.zeros((h, w), np.float32); f = max(4, int(0.12 * min(h, w)))
        mask[f:h - f // 2, f:w - f] = 1; mask = cv2.GaussianBlur(mask, (0, 0), f / 2)[..., None]
        R[py:py + h, px:px + w] = Ts * mask + R[py:py + h, px:px + w] * (1 - mask)
        print(f"box {x0},{y0}: corr {v:.3f} scale {s:.2f} at {px},{py} (dx {px - x0}, dy {py - y0})")
    cv2.imwrite(out_path, R.clip(0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 95])
if __name__ == "__main__":
    paste(sys.argv[1], sys.argv[2])
