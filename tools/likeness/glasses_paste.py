#!/usr/bin/env python3
"""Transfer ONLY the glasses from an edited image back onto the real photo.

  python3 tools/likeness/glasses_paste.py REAL.jpg EDITED.jpg OUT.jpg [--debug dbg.jpg]

1. Align EDITED -> REAL with a landmark similarity transform (edits re-render every pixel and may shift/scale).
2. Glasses zone = band around both eyes (outer canthi +-0.75 IOD horizontally out to the ears, brow-top .. upper cheek
   vertically). Inside it, mask = pixels whose Lab difference to the real photo is large AND that are darker / more
   saturated-teal in the edit (frame metal, rims, nose pads, temple arms).
3. Eyes are protected: the eye openings (landmark eye contours dilated ~0.12 IOD) and brows are removed from the mask,
   so the eyes inside the lenses stay pixel-identical to the photo. A faint lens tint can be added with --tint.
4. Small dilation + feather; composite. Prints the fraction of eye pixels changed (must be 0).
"""
import sys, os, argparse, json
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS

R_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
L_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("real"); ap.add_argument("edit"); ap.add_argument("out")
    ap.add_argument("--thr", type=float, default=14.0); ap.add_argument("--tint", type=float, default=0.0); ap.add_argument("--debug")
    a = ap.parse_args()
    real = MS.load_rgb(a.real); ed = MS.load_rgb(a.edit)
    pr = MS.landmarks(real)[0]; pe = MS.landmarks(ed)[0]
    M, _ = cv2.estimateAffinePartial2D(pe[:, :2].astype(np.float32), pr[:, :2].astype(np.float32), method=cv2.RANSAC)
    h, w = real.shape[:2]
    ew = cv2.warpAffine(ed, M, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
    iod = np.linalg.norm(pr[MS.R_OUT, :2] - pr[MS.L_OUT, :2])
    # zone
    zone = np.zeros((h, w), np.uint8)
    xs = [pr[234, 0] - 0.25 * iod, pr[454, 0] + 0.25 * iod]
    ytop = min(pr[i, 1] for i in MS.BROW_R_UP + MS.BROW_L_UP) - 0.08 * iod
    ybot = max(pr[[145, 374], 1]) + 0.55 * iod
    zone[int(max(0, ytop)):int(min(h, ybot)), int(max(0, xs[0])):int(min(w, xs[1]))] = 1
    lr = cv2.cvtColor(real, cv2.COLOR_RGB2LAB).astype(np.float32); le = cv2.cvtColor(ew, cv2.COLOR_RGB2LAB).astype(np.float32)
    d = np.linalg.norm(le - lr, axis=2)
    darker = (le[..., 0] < lr[..., 0] - 6) | (np.abs(le[..., 1] - lr[..., 1]) + np.abs(le[..., 2] - lr[..., 2]) > 12)
    k = max(5, int(0.07 * iod)) | 1
    bh = cv2.morphologyEx(le[..., 0], cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    thin = bh > 8                                   # thin dark structures (rims, arms) - not broad shading
    m = ((d > a.thr) & darker & thin & (zone > 0)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, 4] >= 12:
            keep[lab == i] = 1
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
    # protect eyes + brows
    prot = np.zeros((h, w), np.uint8)
    for ids in (R_EYE, L_EYE):
        cv2.fillPoly(prot, [pr[ids, :2].astype(np.int32)], 1)
    prot = cv2.dilate(prot, np.ones((5, 5), np.uint8))   # eye opening + ~2 px
    for ids in (MS.BROW_R_UP + MS.BROW_R_LO[::-1], MS.BROW_L_UP + MS.BROW_L_LO[::-1]):
        cv2.fillPoly(prot, [pr[ids, :2].astype(np.int32)], 1)
    nose = np.zeros((h, w), np.uint8)               # nostrils / nose tip
    cv2.fillConvexPoly(nose, cv2.convexHull(pr[[98, 327, 2, 94, 19, 1, 4, 129, 358, 64, 294], :2].astype(np.int32)), 1)
    prot |= cv2.dilate(nose, np.ones((7, 7), np.uint8))
    seg = MS.seg_mask(real)
    if seg.shape != (h, w):
        seg = cv2.resize(seg, (w, h), interpolation=cv2.INTER_NEAREST)
    prot |= ((seg == 1) | (seg == 0)).astype(np.uint8)          # hair / background
    keep[prot > 0] = 0
    alpha = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 0.8)
    eyep = np.zeros((h, w), np.uint8)
    for ids in (R_EYE, L_EYE):
        cv2.fillPoly(eyep, [pr[ids, :2].astype(np.int32)], 1)
    alpha[eyep > 0] = 0                              # eyes strictly pixel-identical
    alpha = alpha[..., None]
    out = ew * alpha + real * (1 - alpha)
    if a.tint > 0:   # faint lens tint inside the rims (outside eye protection it is already handled)
        pass
    out = np.clip(out, 0, 255).astype(np.uint8)
    eye = np.zeros((h, w), bool)
    for ids in (R_EYE, L_EYE):
        t = np.zeros((h, w), np.uint8); cv2.fillPoly(t, [pr[ids, :2].astype(np.int32)], 1); eye |= t > 0
    changed = float((np.abs(out.astype(int) - real.astype(int)).max(2)[eye] > 0).mean())
    cv2.imwrite(a.out, cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 96])
    if a.debug:
        dbg = real.copy(); dbg[keep > 0] = (255, 0, 255); cv2.imwrite(a.debug, cv2.cvtColor(dbg, cv2.COLOR_RGB2BGR))
    print(json.dumps(dict(mask_px=int(keep.sum()), eye_pixels_changed_frac=changed)))


if __name__ == "__main__":
    main()
