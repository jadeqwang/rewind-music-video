#!/usr/bin/env python3
"""Review sheet for a roto-base clip: 6 frames (top 2 rows) + Canny on 2 frames (bottom row), plus edge stats.
Usage: python3 tools/clip_review.py CLIP.mp4 OUT.jpg"""
import sys, cv2, numpy as np
clip, out = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(clip); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
idx = [int(round(i * (n - 1) / 5)) for i in range(6)]
frames = []
for i in idx:
    cap.set(cv2.CAP_PROP_POS_FRAMES, i); ok, f = cap.read()
    frames.append(f if ok else np.zeros((720, 1280, 3), np.uint8))
W = 640; sc = lambda f: cv2.resize(f, (W, int(f.shape[0] * W / f.shape[1])))
tiles = []
for k, f in zip(idx, frames):
    t = sc(f).copy(); cv2.putText(t, f"f{k} {k/24:.2f}s", (8, 22), 0, 0.6, (0, 255, 0), 2); tiles.append(t)
stats = []
canny = []
for f in (frames[1], frames[4]):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
    g = cv2.bilateralFilter(g, 9, 40, 7)
    e = cv2.Canny(g, 60, 150)
    dens = e.mean() / 255
    nc, lab, st, _ = cv2.connectedComponentsWithStats(e, connectivity=8)
    small = int((st[1:, cv2.CC_STAT_AREA] < 15).sum()); big = int((st[1:, cv2.CC_STAT_AREA] >= 80).sum())
    stats.append(f"edge_density={dens:.3f} comps={nc-1} tiny(<15px)={small} long(>=80px)={big}")
    c = cv2.cvtColor(e, cv2.COLOR_GRAY2BGR); canny.append(sc(c))
rows = [np.hstack(tiles[0:3]), np.hstack(tiles[3:6]), np.hstack(canny + [np.zeros_like(canny[0])])]
sheet = np.vstack(rows)
for j, s in enumerate(stats):
    cv2.putText(sheet, s, (8 + 640 * j, rows[0].shape[0] * 2 + 22), 0, 0.45, (0, 200, 255), 1)
cv2.imwrite(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(clip, n, "frames;", " | ".join(stats))
