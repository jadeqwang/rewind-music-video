#!/usr/bin/env python3
"""Paste the REAL face from a photo back onto a generated/edited composite, pixel-exact identity.

  python3 tools/likeness/pasteback.py REAL.jpg COMPOSITE.jpg OUT.jpg [--strength 0.85] [--grow 0.03] [--debug dbg.jpg]

1. Face region in the real photo = convex hull of (MediaPipe face-oval landmarks U selfie-multiclass face-skin
   pixels connected to the face), which includes brows, eyes, glasses, nose, mouth, forehead up to the hairline.
2. Alignment real -> composite: similarity transform from the 478 landmarks of both images (estimateAffinePartial2D,
   RANSAC). If the composite has no detectable face (profiles), fall back to ORB features + RANSAC inside the face box.
3. Grade: per-channel Lab mean/std transfer from the composite's own face (which carries the scene lighting) onto the
   warped real face, blended by --strength (1 = full scene grade, 0 = untouched photo colours).
4. Feathered alpha blend (feather = ~6% face width), mask eroded slightly so hair edges come from the composite.
Returns/prints the alignment residual so a bad fit can be rejected.
"""
import sys, os, argparse, json
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS

FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176,
             149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


def face_mask(rgb, pts=None):
    h, w = rgb.shape[:2]
    seg = MS.seg_mask(rgb)
    if seg.shape != (h, w):
        seg = cv2.resize(seg, (w, h), interpolation=cv2.INTER_NEAREST)
    skin = (seg == 3).astype(np.uint8)
    m = np.zeros((h, w), np.uint8)
    if pts is not None:
        cv2.fillConvexPoly(m, cv2.convexHull(pts[FACE_OVAL, :2].astype(np.int32)), 1)
        # keep the skin component(s) touching the oval
        n, lab = cv2.connectedComponents(skin)
        ids = set(np.unique(lab[(m > 0) & (skin > 0)])) - {0}
        sk = np.isin(lab, list(ids)).astype(np.uint8) if ids else skin * 0
    else:
        n, lab, st, _ = cv2.connectedComponentsWithStats(skin)
        if n < 2:
            return None
        k = 1 + int(np.argmax(st[1:, 4])); sk = (lab == k).astype(np.uint8)
    u = ((m + sk) > 0).astype(np.uint8)
    ys, xs = np.where(u > 0)
    if len(xs) < 100:
        return None
    hull = cv2.convexHull(np.c_[xs, ys].astype(np.int32))
    out = np.zeros((h, w), np.uint8); cv2.fillConvexPoly(out, hull, 1)
    # do not take hair: remove hair pixels (class 1) except inside the landmark oval (brows)
    out[(seg == 1) & (m == 0)] = 0
    return out


def align(src, dst, ps=None, pd=None, box=None):
    if ps is not None and pd is not None:
        M, inl = cv2.estimateAffinePartial2D(ps[:, :2].astype(np.float32), pd[:, :2].astype(np.float32), method=cv2.RANSAC, ransacReprojThreshold=4)
        res = float(np.median(np.linalg.norm((np.c_[ps[:, :2], np.ones(len(ps))] @ M.T) - pd[:, :2], axis=1)))
        return M, res, "landmarks"
    g1 = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY); g2 = cv2.cvtColor(dst, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(6000)
    mk = None
    if box is not None:
        mk = np.zeros_like(g1); x0, y0, x1, y1 = box; mk[y0:y1, x0:x1] = 255
    k1, d1 = orb.detectAndCompute(g1, mk); k2, d2 = orb.detectAndCompute(g2, None)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    mt = [m for m, n in bf.knnMatch(d1, d2, k=2) if m.distance < 0.78 * n.distance]
    if len(mt) < 12:
        return None, None, "orb-fail"
    a = np.float32([k1[m.queryIdx].pt for m in mt]); b = np.float32([k2[m.trainIdx].pt for m in mt])
    M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=5)
    r = np.linalg.norm((np.c_[a, np.ones(len(a))] @ M.T) - b, axis=1)[inl.ravel() > 0]
    return M, float(np.median(r)), f"orb({int(inl.sum())} inliers)"


def lab_transfer(src, ref, mask, strength):
    s = cv2.cvtColor(src, cv2.COLOR_RGB2LAB).astype(np.float32); r = cv2.cvtColor(ref, cv2.COLOR_RGB2LAB).astype(np.float32)
    mm = mask > 0
    out = s.copy()
    for c in range(3):
        ms, ss = s[..., c][mm].mean(), s[..., c][mm].std() + 1e-3
        mr, sr = r[..., c][mm].mean(), r[..., c][mm].std() + 1e-3
        t = (s[..., c] - ms) * (sr / ss) + mr
        out[..., c] = s[..., c] * (1 - strength) + t * strength
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def pasteback(real_path, comp, strength=0.85, grow=0.035, src_flip=False, debug=None):
    src = MS.load_rgb(real_path)
    if src_flip:
        src = np.ascontiguousarray(src[:, ::-1])
    dst = MS.load_rgb(comp) if isinstance(comp, str) else comp
    ls, ld = MS.landmarks(src), MS.landmarks(dst)
    ps = ls[0] if ls else None; pd = ld[0] if ld else None
    msk = face_mask(src, ps)
    if msk is None:
        raise SystemExit("no face region in real photo")
    ys, xs = np.where(msk > 0); box = (xs.min(), ys.min(), xs.max(), ys.max())
    M, res, how = align(src, dst, ps, pd, box)
    if M is None:
        raise SystemExit("alignment failed: " + how)
    h, w = dst.shape[:2]
    ws = cv2.warpAffine(src, M, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
    wm = cv2.warpAffine(msk * 255, M, (w, h), flags=cv2.INTER_LINEAR)
    fw = max(20, (box[2] - box[0]) * float(np.sqrt(abs(np.linalg.det(M[:, :2])))))
    k = max(3, int(abs(grow) * fw)) | 1
    # grow < 0: erode (hair edges from the composite); grow > 0: dilate so the REAL silhouette (cheeks/jaw
    # contour) replaces the generated one - otherwise a wider generated face leaks into the outline
    wm = cv2.erode(wm, np.ones((k, k), np.uint8)) if grow < 0 else cv2.dilate(wm, np.ones((k, k), np.uint8))
    f = max(3, int(0.06 * fw)) | 1
    alpha = cv2.GaussianBlur(wm.astype(np.float32) / 255, (0, 0), f / 2.5)[..., None]
    graded = lab_transfer(ws, dst, wm > 128, strength)
    out = (graded * alpha + dst * (1 - alpha)).astype(np.uint8)
    info = dict(align=how, residual_px=round(res, 2), scale=round(float(np.sqrt(abs(np.linalg.det(M[:, :2])))), 3), face_px=round(fw, 1))
    if debug:
        d = out.copy(); cnt, _ = cv2.findContours((wm > 128).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(d, cnt, -1, (0, 255, 0), 1); cv2.imwrite(debug, cv2.cvtColor(d, cv2.COLOR_RGB2BGR))
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real"); ap.add_argument("comp"); ap.add_argument("out")
    ap.add_argument("--strength", type=float, default=0.85); ap.add_argument("--grow", type=float, default=0.035)
    ap.add_argument("--flip", action="store_true", help="mirror the real photo first (only for continuity; flips brow asymmetry)")
    ap.add_argument("--debug")
    a = ap.parse_args()
    out, info = pasteback(a.real, a.comp, a.strength, a.grow, a.flip, a.debug)
    cv2.imwrite(a.out, cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(json.dumps(info))


if __name__ == "__main__":
    main()
