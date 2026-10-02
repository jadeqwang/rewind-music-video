#!/usr/bin/env python3
"""Deterministic landmark-driven likeness correction for Jade (eyes, forehead/hairline, face shape).

  python3 tools/likeness/warp.py IN.jpg OUT.jpg [--iters 3] [--no-eyes] [--no-forehead] [--no-shape] [--report out.json]

All corrections are one smooth backward map (cv2.remap, Lanczos), built from MediaPipe landmarks:
  * eyes: anisotropic scale about each eye centre (sx, sy) inside an ellipse (full strength within the eye,
    smoothstep falloff to identity at ~0.8 eye-width horizontally / 0.4 vertically) so glasses rims move
    < 1 px and the brows do not move at all -> brow asymmetry is untouched.
  * upper head: everything above the brow line (forehead + cranium + hair mass) is scaled up as ONE unit
    about a pivot just above the brows (top_scale; top_h scales the horizontal part), smooth ramp so brows,
    glasses, eyes, nose, mouth and jaw are untouched -> the hairline rises because the head grows, not
    because the hair recedes. Solved from the forehead ratio and upper_head (brow->top of head / brow->chin).
  * shape (heart / melon-seed): optional narrowing of the lower jaw/chin (below the mouth) about the face axis
    if a gen drifts round/square (jaw_narrow).
Parameters are solved iteratively: warp the ORIGINAL with updated params, re-measure, repeat (no compounding resampling).
Never shrinks the eyes: eye factors are clamped to >= 1.
"""
import sys, os, json, math, argparse
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS

R_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
L_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def build_map(shape, pts, P):
    """P: dict(eye_sx, eye_sy, dh (px), top_widen, jaw_narrow). Returns map_x, map_y (backward)."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    mx, my = xx.copy(), yy.copy()
    up, right = MS.face_frame(pts)
    g = pts[MS.GLABELLA, :2]
    fw = float(np.linalg.norm(pts[MS.CHEEK_L, :2] - pts[MS.CHEEK_R, :2]))
    # face-axis coords of every pixel
    dx, dy = xx - g[0], yy - g[1]
    u = dx * up[0] + dy * up[1]          # along up axis (px above glabella)
    v = dx * right[0] + dy * right[1]    # across
    ax = lambda i: float(np.dot(pts[i, :2] - g, up))
    brow_top = max(ax(i) for i in MS.BROW_R_UP + MS.BROW_L_UP)
    chin = ax(MS.CHIN)
    # ---- upper head: scale everything above the brow line as one unit (forehead + cranium + hair) ----
    ts = P.get("top_scale", 1.0)
    if abs(ts - 1) > 1e-4:
        u0 = brow_top + 0.02 * fw                       # pivot just above the brow tops: brows stay put
        wgt = smooth((u - u0) / (0.14 * fw))             # 0 at/below brows -> 1 by mid-forehead
        wgt = wgt * (1 - smooth((np.abs(v) - 1.0 * fw) / (0.5 * fw)))   # identity far to the sides
        se = 1 + (ts - 1) * wgt
        su = u0 + (u - u0) / se                          # vertical: sample closer to the pivot
        sv = v / (1 + (ts - 1) * wgt * P.get("top_h", 1.0))
        mx += ((su - u) * up[0] + (sv - v) * right[0]).astype(np.float32)
        my += ((su - u) * up[1] + (sv - v) * right[1]).astype(np.float32)
    jn = P.get("jaw_narrow", 0.0)
    if abs(jn) > 1e-4:
        mouth = ax(13)
        wgt = smooth((mouth - u) / max(1, (mouth - chin))) * (1 - smooth((chin - 0.15 * fw - u) / (0.15 * fw)))
        wgt *= 1 - smooth((np.abs(v) - 0.65 * fw) / (0.3 * fw))
        s = 1 - jn * wgt
        nv = v / s - v
        mx += (nv * right[0]).astype(np.float32); my += (nv * right[1]).astype(np.float32)
    # ---- eyes ----
    sx, sy = P.get("eye_sx", 1.0), P.get("eye_sy", 1.0)
    if sx > 1.0005 or sy > 1.0005:
        for ids, (o, i) in ((R_EYE, (MS.R_OUT, MS.R_IN)), (L_EYE, (MS.L_OUT, MS.L_IN))):
            c = pts[ids, :2].mean(0)
            ew = float(np.linalg.norm(pts[o, :2] - pts[i, :2]))
            ex = pts[i, :2] - pts[o, :2]; ex /= np.linalg.norm(ex); ey = np.array([-ex[1], ex[0]])
            # use the original sample position (after other warps) is negligible; operate in output coords
            px, py = xx - c[0], yy - c[1]
            a = px * ex[0] + py * ex[1]; b = px * ey[0] + py * ey[1]
            r = np.sqrt((a / (0.80 * ew)) ** 2 + (b / (0.40 * ew)) ** 2)
            wgt = 1 - smooth((r - 0.62) / 0.38)       # 1 inside eye (r<0.62), 0 at r>=1
            fx = 1 + (sx - 1) * wgt; fy = 1 + (sy - 1) * wgt
            na, nb = a / fx - a, b / fy - b
            mx += (na * ex[0] + nb * ey[0]).astype(np.float32); my += (na * ex[1] + nb * ey[1]).astype(np.float32)
    return mx, my


def apply(rgb, pts, P):
    mx, my = build_map(rgb.shape, pts, P)
    return cv2.remap(rgb, mx, my, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)


def correct(rgb, ref=None, iters=3, eyes=True, forehead=True, shape=True, verbose=True, eye_tol=0.01, fh_tol=0.01):
    ref = ref or MS.real_ref()
    lm = MS.landmarks(rgb)
    if lm is None:
        return rgb, None, None
    pts = lm[0]
    m0 = MS.measure(rgb)
    up, _ = MS.face_frame(pts)
    g = pts[MS.GLABELLA, :2]
    ax = lambda i: float(np.dot(pts[i, :2] - g, up))
    brow = float(np.mean([ax(i) for i in MS.BROW_R + MS.BROW_L])); chin = ax(MS.CHIN)
    hp = m0.get("hairline_xy")
    P = dict(eye_sx=1.0, eye_sy=1.0, top_scale=1.0, top_h=1.0, jaw_narrow=0.0,
             hair_u=float(np.dot(np.array(hp) - g, up)) if hp else brow + 0.45 * (brow - chin))
    m, out, hist = m0, rgb, []
    for it in range(iters):
        changed = False
        if eyes:
            # size: eye width & iris (lid-independent) vs face width; shape: opening ratio
            want = []
            if m.get("eye_w_face"): want.append(ref["eye_w_face"] / m["eye_w_face"])
            if m.get("iris_face"): want.append(ref["iris_face"] / m["iris_face"])
            k = max(1.0, float(np.exp(np.mean(np.log(want))))) if want else 1.0
            ko = max(1.0, ref["eye_open"] / m["eye_open"]) if m.get("eye_open") else 1.0
            if k > 1 + eye_tol or ko > 1 + eye_tol:
                P["eye_sx"] = min(1.18, P["eye_sx"] * k)
                P["eye_sy"] = min(1.30, P["eye_sy"] * k * ko)
                changed = True
        if forehead:
            want = []
            if m.get("forehead") and ref.get("forehead"):
                f, ft = m["forehead"], ref["forehead"]
                want.append((ft / (1 - ft)) / (f / (1 - f)))       # hair-brow span / brow-chin span
            if m.get("upper_head") and ref.get("upper_head"):
                want.append(ref["upper_head"] / m["upper_head"])
            if want:
                k = float(np.exp(np.mean(np.log(want))))
                too_big = (m.get("forehead") or 0) > 1.08 * ref["forehead"] or (m.get("upper_head") or 0) > 1.12 * ref.get("upper_head", 9)
                if k > 1 + fh_tol or (k < 1 and too_big):   # never shrink a large forehead unless beyond the gate
                    P["top_scale"] = float(np.clip(P["top_scale"] * k, 0.95, 1.25)); changed = True
        if shape and ref.get("forehead_w") and m.get("forehead_w"):
            jr = m["jaw_w"] / ref["jaw_w"] - 1 if m.get("jaw_w") else 0
            if jr > 0.02:
                P["jaw_narrow"] = min(0.06, P["jaw_narrow"] + jr * 0.8); changed = True
        if not changed:
            break
        out = apply(rgb, pts, P)
        m = MS.measure(out)
        hist.append(dict(params={k: round(v, 4) for k, v in P.items()}, m={k: m.get(k) for k in MS.KEYS}))
        if verbose:
            print("iter", it, hist[-1]["params"], {k: m.get(k) for k in ("eye_w_face", "iris_face", "eye_open", "forehead", "upper_head", "forehead_w", "jaw_w")})
    return out, P, dict(before=m0, after=m, hist=hist)


def correct_multi(rgb, iters=3, max_yaw=35, **kw):
    """Correct every face of a multi-panel sheet: each face is solved on its own Voronoi cell and the
    corrected cell is pasted back (warps are identity well before the cell borders). Faces with
    |yaw| > max_yaw (profiles) are left untouched - the mesh is unreliable there - and reported."""
    faces = MS.all_faces(rgb)
    if len(faces) <= 1:
        out, P, rep = correct(rgb, iters=iters, **kw)
        return out, [dict(params=P, report=rep)]
    lab = MS.face_cells(rgb, faces)
    out = rgb.copy(); reps = []
    for i, f in enumerate(faces):
        ys, xs = np.where(lab == i)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        if abs(f["yaw"]) > max_yaw:
            reps.append(dict(face=i, skipped=f"yaw {f['yaw']:.0f}")); continue
        bg = np.median(np.r_[rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]], 0).astype(np.uint8)
        sub = rgb[y0:y1, x0:x1].copy(); sub[lab[y0:y1, x0:x1] != i] = bg
        sub = np.ascontiguousarray(sub)
        fixed, P, rep = correct(sub, iters=iters, verbose=False, **kw)
        if P is None:
            reps.append(dict(face=i, skipped="no face in cell")); continue
        msk = (lab[y0:y1, x0:x1] == i)
        out[y0:y1, x0:x1][msk] = fixed[msk]
        reps.append(dict(face=i, params={k: round(v, 4) for k, v in P.items()},
                         before={k: rep["before"].get(k) for k in MS.KEYS}, after={k: rep["after"].get(k) for k in MS.KEYS}))
    return out, reps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--no-eyes", action="store_true"); ap.add_argument("--no-forehead", action="store_true")
    ap.add_argument("--no-shape", action="store_true"); ap.add_argument("--report")
    ap.add_argument("--multi", action="store_true", help="character sheet with several faces")
    a = ap.parse_args()
    rgb = MS.load_rgb(a.inp)
    if a.multi:
        out, reps = correct_multi(rgb, iters=a.iters, eyes=not a.no_eyes, forehead=not a.no_forehead, shape=not a.no_shape)
        cv2.imwrite(a.out, cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
        if a.report:
            json.dump(reps, open(a.report, "w"), indent=1, default=float)
        for r in reps: print(r.get("face"), r.get("params") or r.get("skipped"))
        return
    out, P, rep = correct(rgb, iters=a.iters, eyes=not a.no_eyes, forehead=not a.no_forehead, shape=not a.no_shape)
    cv2.imwrite(a.out, cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    if a.report:
        json.dump(dict(params=P, **(rep or {})), open(a.report, "w"), indent=1, default=float)
    print("params", P)


if __name__ == "__main__":
    main()
