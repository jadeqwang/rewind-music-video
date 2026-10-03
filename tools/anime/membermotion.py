#!/usr/bin/env python3
"""Per-member residual motion for multi-person shots with camera moves (committee). Frames t, t+step are aligned with an
ECC affine (removes push-in/pan), then the mean abs difference is taken inside each member box (frame-0 boxes carried by the
cumulative affine). Prints per member: mean residual, % of frame pairs with residual > thr ("moving").
  membermotion.py CLIP.mp4 --boxes "x0,y0,x1,y1;..." (frame-0 px) [--step 3] [--thr 1.2]"""
import sys, argparse, numpy as np, cv2
ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--boxes", required=True)
ap.add_argument("--step", type=int, default=3); ap.add_argument("--thr", type=float, default=1.2); a = ap.parse_args()
B = [list(map(float, b.split(","))) for b in a.boxes.split(";")]
cap = cv2.VideoCapture(a.clip); F = []
while True:
    ok, f = cap.read()
    if not ok: break
    F.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
h, w = F[0].shape; S = 0.5
def ecc(src, dst):
    W = np.eye(2, 3, dtype=np.float32); s = cv2.resize(src, None, fx=S, fy=S); d = cv2.resize(dst, None, fx=S, fy=S)
    _, W = cv2.findTransformECC(d, s, W, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5), None, 5)
    W[:, 2] /= S; return W                     # maps dst coords -> src coords
cum = np.eye(3); res = {i: [] for i in range(len(B))}
for t in range(0, len(F) - a.step, a.step):
    W = ecc(F[t], F[t + a.step])               # x_t = W @ x_{t+step}
    al = cv2.warpAffine(F[t + a.step], W, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP) if False else \
         cv2.warpAffine(F[t], cv2.invertAffineTransform(W), (w, h))   # frame t brought into t+step coords
    D = np.abs(al - F[t + a.step])
    Wi = np.vstack([cv2.invertAffineTransform(W), [0, 0, 1]])        # t -> t+step
    for i, (x0, y0, x1, y1) in enumerate(B):
        p = cum @ np.array([[x0, x1], [y0, y1], [1, 1]])            # box in frame-t coords
        X0, X1 = int(max(0, p[0, 0])), int(min(w, p[0, 1])); Y0, Y1 = int(max(0, p[1, 0])), int(min(h, p[1, 1]))
        q = Wi @ np.array([[X0, X1], [Y0, Y1], [1, 1]])
        X0, X1 = int(max(4, q[0, 0])), int(min(w - 4, q[0, 1])); Y0, Y1 = int(max(4, q[1, 0])), int(min(h - 4, q[1, 1]))
        if X1 - X0 > 10 and Y1 - Y0 > 10: res[i].append(float(D[Y0:Y1, X0:X1].mean()))
    cum = Wi @ cum
for i in range(len(B)):
    r = np.array(res[i]) if res[i] else np.zeros(1)
    print(f"member {i + 1}: mean {r.mean():.2f}  p90 {np.percentile(r, 90):.2f}  moving {100 * (r > a.thr).mean():.0f}%  pairs {len(res[i])}")
