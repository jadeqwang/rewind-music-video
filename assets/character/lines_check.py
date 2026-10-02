"""Sanity-check redraw: flat bone-white silhouette + sparse feature lines (eyes, brows, nose tip, lips, glasses, contours)."""
import cv2, numpy as np, sys, facetools as ft
src, panel, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
im = cv2.imread(src); f = ft.faces(im)[panel]
npan = int(sys.argv[4]) if len(sys.argv) > 4 else 4; pw = im.shape[1] / npan; k = int((f[0] + f[2] / 2) // pw)
bgc = np.median(im[:15, int(k*pw)+5:int((k+1)*pw)-5].reshape(-1, 3), 0)
im = im.copy(); im[:, :int(k*pw)+3] = bgc; im[:, int((k+1)*pw)-3:] = bgc
x, y, w, h = f[:4]; cx, cy = x + w/2, y + h/2; s = max(w, h) * 2.2; size = 720
M = np.float32([[size/s, 0, size/2 - cx*size/s], [0, size/s, size/2 - cy*size/s]])
c = cv2.warpAffine(im, M, (size, size), borderValue=tuple(float(v) for v in bgc))
lm = (f[4:14].reshape(5, 2) @ M[:, :2].T + M[:, 2])  # re, le, nose, mouth r, mouth l
eyeR, eyeL, nose, mR, mL = lm; iod = np.linalg.norm(eyeL - eyeR)
# silhouette: anything differing from the (gray) background sampled at the top corners
bg = np.median(np.vstack([c[:20, :20].reshape(-1, 3), c[:20, -20:].reshape(-1, 3)]), 0)
diff = np.linalg.norm(c.astype(float) - bg, axis=2); sil = (diff > 28).astype(np.uint8)
sil = cv2.morphologyEx(sil, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); n, lab, st, _ = cv2.connectedComponentsWithStats(sil)
sil = (lab == 1 + np.argmax(st[1:, 4])).astype(np.uint8) * 255
g = cv2.bilateralFilter(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), 9, 40, 9)
e = cv2.Canny(g, 40, 110)
mask = np.zeros_like(e)
for p in (eyeR, eyeL):
    cv2.ellipse(mask, tuple(int(v) for v in p), (int(iod*.56), int(iod*.33)), 0, 0, 360, 255, -1)          # eye + glasses rim
    cv2.ellipse(mask, (int(p[0]), int(p[1]-iod*.42)), (int(iod*.40), int(iod*.14)), 0, 0, 360, 255, -1)  # brow
cv2.circle(mask, tuple(int(v) for v in nose + [0, iod*.12]), int(iod*.16), 255, -1)                       # nose tip
mc = (mR + mL) / 2; cv2.ellipse(mask, tuple(int(v) for v in mc), (int(iod*.45), int(iod*.2)), 0, 0, 360, 255, -1)
cv2.line(mask, tuple(int(v) for v in eyeR), tuple(int(v) for v in eyeL), 255, int(iod*.12))                # glasses bridge
feat = cv2.bitwise_and(e, mask)
# drop tiny fragments (texture) — keep connected strokes only
n, lab, st, _ = cv2.connectedComponentsWithStats(feat, connectivity=8)
keep = np.isin(lab, [i for i in range(1, n) if st[i, 4] >= 18]); feat = keep.astype(np.uint8) * 255
# hair: hair region = dark pixels inside silhouette; draw its outline + face/hair boundary
hair = ((g < 60) & (sil > 0)).astype(np.uint8) * 255; hair = cv2.morphologyEx(hair, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
cont = cv2.Canny(sil, 50, 150) | cv2.Canny(hair, 50, 150)
lines = cv2.dilate(feat | cont, np.ones((2, 2), np.uint8))
BONE, INK = (216, 230, 236), (10, 8, 7)
r = np.zeros_like(c); r[:] = INK; r[sil > 0] = BONE; r[lines > 0] = INK
r[(lines > 0) & (sil == 0)] = BONE
cv2.imwrite(out, np.hstack([c, r]), [cv2.IMWRITE_JPEG_QUALITY, 90])
print("iod", round(float(iod), 1), "feature px", int((feat > 0).sum()), "out", out)
