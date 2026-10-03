#!/usr/bin/env python3
"""Rewind-twirl direction check for anime clips. Tracks the hand as the largest skin-coloured blob outside the face box
(face box from frame 0 via framemeasure.find_face, grown downward to cover the neck), per frame; then measures the winding of
the hand path around its moving centre (1 s running mean). Screen convention: CCW as seen by the viewer = POSITIVE turns.
  twirl.py CLIP.mp4 [--t0 0 --t1 5] [--png out.png]   -> prints turns_ccw (signed), per-window turns, track coverage"""
import sys, argparse, numpy as np, cv2
sys.path.insert(0, "/home/user/rewind-music-video/tools/anime"); import framemeasure as FM
ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--t0", type=float, default=0); ap.add_argument("--t1", type=float, default=99)
ap.add_argument("--png"); a = ap.parse_args()
cap = cv2.VideoCapture(a.clip); fps = cap.get(cv2.CAP_PROP_FPS) or 24; frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
h, w = frames[0].shape[:2]
# skin reference = median colour of the face centre on frame 0
box = FM.find_face(cv2.cvtColor(frames[0], cv2.COLOR_BGR2RGB)); x0, y0, x1, y1 = [int(v) for v in box]
fw, fh = x1 - x0, y1 - y0
lab0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2LAB).astype(np.float32)
ref = np.median(lab0[y0 + fh // 3:y0 + 2 * fh // 3, x0 + fw // 4:x1 - fw // 4].reshape(-1, 3), 0)
def skin(f):
    lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB).astype(np.float32)
    d = np.sqrt(((lab[..., 1:] - ref[1:]) ** 2).sum(-1)) + 0.25 * np.abs(lab[..., 0] - ref[0])
    return (d < 14).astype(np.uint8)
SK = [skin(f) for f in frames]
static = cv2.dilate((np.mean(SK, 0) > 0.6).astype(np.uint8), np.ones((9, 9), np.uint8))   # belly / neck skin that never moves
pts = []
for i, f in enumerate(frames):
    t = i / fps
    if t < a.t0 or t > a.t1: pts.append(None); continue
    m = SK[i] * (1 - static)
    fb = FM.find_face(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) or box          # current face (falls back to frame 0)
    X0, Y0, X1, Y1 = [int(v) for v in fb]; gw = (X1 - X0) // 8
    m[max(0, Y0 - fh // 2):min(h, Y1 + int(0.35 * fh)), max(0, X0 - gw):min(w, X1 + gw)] = 0      # face + neck
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lb, st, cen = cv2.connectedComponentsWithStats(m)
    if n < 2: pts.append(None); continue
    j = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    if st[j, cv2.CC_STAT_AREA] < 0.05 * fw * fh: pts.append(None); continue
    ys, xs = np.nonzero(lb == j); top = np.argsort(ys)[:max(5, len(ys) // 10)]      # upper tip of the hand blob (finger)
    pts.append((float(xs[top].mean()), float(ys[top].mean())))
idx = [i for i, p in enumerate(pts) if p is not None]; cov = len(idx) / max(1, sum(1 for i in range(len(frames)) if a.t0 <= i / fps <= a.t1))
P = np.array([pts[i] for i in idx]); T = np.array(idx) / fps
if len(P) < 8: print("too few hand frames", len(P)); sys.exit()
k = max(3, int(fps * 0.6)); ker = np.ones(k) / k
C = np.stack([np.convolve(np.pad(P[:, q], k, mode="edge"), ker, "same")[k:-k] for q in (0, 1)], 1)
ang = np.unwrap(np.arctan2(-(P[:, 1] - C[:, 1]), P[:, 0] - C[:, 0]))       # y flipped: CCW on screen = +
dA = np.diff(ang); r = np.linalg.norm(P - C, axis=1); valid = (r[1:] > 4) & (np.diff(T) < 0.15)
turns = float(dA[valid].sum() / (2 * np.pi))
win = [(round(T[i], 2), round(float(dA[i:i + 12][valid[i:i + 12]].sum() / (2 * np.pi)), 2)) for i in range(0, len(dA), 12)]
print(f"turns_ccw {turns:+.2f}  coverage {cov:.2f}  frames {len(P)}  radius_med {np.median(r):.1f}px")
print("windows (t, turns):", win)
if a.png:
    im = frames[len(frames) // 2].copy()
    for i in range(1, len(P)):
        c = (int(255 * i / len(P)), 80, 255 - int(255 * i / len(P)))
        cv2.line(im, tuple(P[i - 1].astype(int)), tuple(P[i].astype(int)), c, 2)
    cv2.imwrite(a.png, im)
