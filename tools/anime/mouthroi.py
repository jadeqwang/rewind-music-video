#!/usr/bin/env python3
"""Mouth ROI (x y w h, frame px) for lipsync.py --roi on anime clips: find the face on frame N (windowed, gamma-lifted), landmarks on an upscaled crop."""
import sys, numpy as np, cv2
sys.path.insert(0, "/home/user/rewind-music-video/tools/anime"); sys.path.insert(0, "/home/user/rewind-music-video/tools/likeness")
import framemeasure as FM, measure as MS
cap = cv2.VideoCapture(sys.argv[1]); cap.set(cv2.CAP_PROP_POS_FRAMES, int(sys.argv[2]) if len(sys.argv) > 2 else 0)
ok, fr = cap.read(); rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB); h, w = rgb.shape[:2]
x0, y0, x1, y1 = FM.find_face(rgb); s = max(x1 - x0, y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
X0, Y0 = int(max(0, cx - s)), int(max(0, cy - s)); X1, Y1 = int(min(w, cx + s)), int(min(h, cy + s))
crop = rgb[Y0:Y1, X0:X1]; sc = 700 / max(crop.shape[:2]); big = cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
if big.mean() < 70: big = FM.lift(big)
p = MS.landmarks(np.ascontiguousarray(big))[0][:, :2] / sc + [X0, Y0]
c = (p[13] + p[14]) / 2; mw = np.linalg.norm(p[61] - p[291]); s = 0.6 * mw + 4
print(int(c[0] - s), int(c[1] - 0.6 * s), int(2 * s), int(1.2 * s))
