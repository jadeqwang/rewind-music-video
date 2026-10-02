#!/usr/bin/env python3
"""Jade's canonical eye / brow / crease template (LIKENESS_RULES: footage landmarks are anchors only).

Seedance shrinks her eyes progressively within a clip (iris -7..-19 %, opening -12..-45 % vs her real photos), so the
redraw never traces the footage eyes. Instead:
  front template  (jade_front.json): built from her REAL core photos (assets/character/v2/measure.json real.core_files).
     MediaPipe landmarks de-rotated with each photo's facial transformation matrix (same convention as
     tools/likeness/measure.py: y up, z toward camera), origin = midpoint of the outer canthi, unit = outer-canthal
     distance (IOD). Lids + iris = per-index mean over the core photos. Brows = PIXEL-level contours (the mesh is
     too prior-smoothed to show her asymmetry) from a canthus-aligned crop, resampled medial->lateral and averaged
     per side; each side is kept separately (never mirrored). Image-left = HER RIGHT brow (un-mirrored refs).
  profile template (jade_profile.json): hand-annotated on refs/jade/PXL_20260929_003030232.jpg (left-facing 3/4
     profile, near eye only), in that photo's pixels, with anchors E (iris centre) and N (nose tip).
  python3 tools/roto/template.py build      # rebuild jade_front.json (+ a debug sheet in tools/roto/templates/)
"""
import os, sys, json, math
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
TPL = os.path.join(HERE, 'templates')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'likeness'))

EYE_R_UP = [33, 246, 161, 160, 159, 158, 157, 173, 133]
EYE_R_LO = [33, 7, 163, 144, 145, 153, 154, 155, 133]
EYE_L_UP = [263, 466, 388, 387, 386, 385, 384, 398, 362]
EYE_L_LO = [263, 249, 390, 373, 374, 380, 381, 382, 362]
IRIS_R, IRIS_L = [468, 469, 470, 471, 472], [473, 474, 475, 476, 477]
BROW_R_UP, BROW_R_LO = [107, 66, 105, 63, 70], [55, 65, 52, 53, 46]
BROW_L_UP, BROW_L_LO = [336, 296, 334, 293, 300], [285, 295, 282, 283, 276]
NB = 24   # brow samples per contour


def canon(pts, M):
    """pixel landmarks (N,3) + transformation matrix -> canonical (N,3): y up, de-rotated, eye-mid origin, IOD unit."""
    R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
    P = pts.copy(); P[:, 1] *= -1; P[:, 2] *= -1
    Pc = (P - P.mean(0)) @ R
    o = (Pc[33] + Pc[263]) / 2
    iod = np.linalg.norm(Pc[33] - Pc[263])
    return (Pc - o) / iod, R, iod


def brow_contours(rgb, pts):
    """Pixel brow contours (tops / bottoms) on a canthus-aligned crop (IOD 200 px, canthi mid at 200,200).
    Returns {'R': (up NBx2, lo NBx2), 'L': ...} in 2-D canonical units (x right, y up, IOD = 1), medial -> lateral."""
    import measure as MS
    A, Mw = MS.align_face(rgb, pts)
    P = (Mw @ np.c_[pts[:, :2], np.ones(len(pts))].T).T
    g = cv2.GaussianBlur(cv2.cvtColor(A, cv2.COLOR_RGB2GRAY).astype(np.float32), (3, 3), 0)
    gl = P[9]
    skin = np.median(g[int(gl[1]) - 40:int(gl[1]) - 15, int(gl[0]) - 15:int(gl[0]) + 15])
    thr = skin - max(14, 0.20 * skin)
    out = {}
    for side, ups, los in (('R', BROW_R_UP, BROW_R_LO), ('L', BROW_L_UP, BROW_L_LO)):
        U, Lo = P[ups], P[los]
        ou, ol = np.argsort(U[:, 0]), np.argsort(Lo[:, 0])
        x0, x1 = int(min(U[:, 0].min(), Lo[:, 0].min())) - 8, int(max(U[:, 0].max(), Lo[:, 0].max())) + 8
        xs, tops, bots = [], [], []
        for x in range(max(x0, 0), min(x1, 399)):
            yu = np.interp(x, U[ou, 0], U[ou, 1]); yl = np.interp(x, Lo[ol, 0], Lo[ol, 1])
            ya, yb = int(yu - 12), int(yl + 4)
            idx = np.where(g[max(ya, 0):yb, x] < thr)[0]
            if len(idx) < 3:
                continue
            runs = np.split(idx, np.where(np.diff(idx) > 2)[0] + 1)
            r = max(runs, key=len)
            if len(r) < 3:
                continue
            xs.append(x); tops.append(r[0] + max(ya, 0)); bots.append(r[-1] + max(ya, 0))
        if len(xs) < 25:
            out[side] = None; continue
        xs, tops, bots = map(np.array, (xs, tops, bots))
        th = bots - tops; ok = th < np.median(th) * 2.2
        xs, tops, bots = xs[ok], tops[ok].astype(float), bots[ok].astype(float)
        k = 7
        tops = np.convolve(np.pad(tops, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]
        bots = np.convolve(np.pad(bots, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]
        # medial -> lateral: image-left brow (R) runs right->left
        order = np.argsort(-xs) if side == 'R' else np.argsort(xs)
        xs, tops, bots = xs[order], tops[order], bots[order]
        t = np.linspace(0, 1, NB); u = np.linspace(0, 1, len(xs))
        X = np.interp(t, u, xs); T_ = np.interp(t, u, tops); B_ = np.interp(t, u, bots)
        f = lambda X, Y: np.stack([(X - 200) / 200, -(Y - 200) / 200], 1)
        out[side] = (f(X, T_), f(X, B_))
    return out


def build():
    import measure as MS
    real = json.load(open(os.path.join(ROOT, 'assets', 'character', 'v2', 'measure.json')))['real']
    files = real['core_files']
    C, brows, used = [], {'R': [], 'L': []}, []
    for fn in files:
        rgb = MS.load_rgb(os.path.join(ROOT, 'refs', 'jade', fn))
        if max(rgb.shape[:2]) > 1600:
            k = 1600 / max(rgb.shape[:2]); rgb = cv2.resize(rgb, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        lm = MS.landmarks(rgb)
        if lm is None:
            continue
        pts, M, bs = lm
        c, R, iod = canon(pts, M)
        C.append(c); used.append(fn)
        b = brow_contours(rgb, pts)
        for s in 'RL':
            if b.get(s) is not None:
                brows[s].append(b[s])
    C = np.mean(C, 0)
    tpl = dict(source=used, units='IOD (outer canthi 33-263), y up, origin = canthi midpoint, de-rotated 3-D',
               iod_over_fw=float(real['mean']['eye_w_face'] / real['mean']['eye_w_iod']),
               eye_open_real=real['mean']['eye_open'], iris_face_real=real['mean']['iris_face'])
    for s, up, lo, ir in (('R', EYE_R_UP, EYE_R_LO, IRIS_R), ('L', EYE_L_UP, EYE_L_LO, IRIS_L)):
        tpl[f'eye_{s}_up'] = C[up].round(5).tolist(); tpl[f'eye_{s}_lo'] = C[lo].round(5).tolist()
        ic = C[ir[0]]; rad = float(np.mean([np.linalg.norm(C[j, :2] - ic[:2]) for j in ir[1:]]))
        tpl[f'iris_{s}'] = [*ic.round(5).tolist(), round(rad, 5)]
        ups, los = BROW_R_UP if s == 'R' else BROW_L_UP, BROW_R_LO if s == 'R' else BROW_L_LO
        zb = np.interp(np.linspace(0, 1, NB), np.linspace(0, 1, 5), (C[ups, 2] + C[los, 2]) / 2)
        if brows[s]:
            U = np.mean([b[0] for b in brows[s]], 0); L = np.mean([b[1] for b in brows[s]], 0)
        else:   # fallback: mesh brow
            U = np.array([np.interp(np.linspace(0, 1, NB), np.linspace(0, 1, 5), C[ups, i]) for i in range(2)]).T
            L = np.array([np.interp(np.linspace(0, 1, NB), np.linspace(0, 1, 5), C[los, i]) for i in range(2)]).T
        tpl[f'brow_{s}_up'] = np.c_[U, zb].round(5).tolist(); tpl[f'brow_{s}_lo'] = np.c_[L, zb].round(5).tolist()
        tpl[f'brow_{s}_n'] = len(brows[s])
    # measured opening of the template eyes (should match the real mean)
    op = []
    for s, up, lo in (('R', EYE_R_UP, EYE_R_LO), ('L', EYE_L_UP, EYE_L_LO)):
        U, L = np.array(tpl[f'eye_{s}_up']), np.array(tpl[f'eye_{s}_lo'])
        op.append(np.mean(np.linalg.norm(U[3:6, :2] - L[3:6, :2], axis=1)) / np.linalg.norm(U[0, :2] - U[-1, :2]))
    tpl['eye_open_template'] = round(float(np.mean(op)), 4)
    os.makedirs(TPL, exist_ok=True)
    json.dump(tpl, open(os.path.join(TPL, 'jade_front.json'), 'w'), indent=0)
    # debug sheet: the template drawn flat at IOD = 400 px
    can = np.full((420, 900, 3), 255, np.uint8)
    T = lambda P: np.round(np.c_[450 + np.asarray(P)[:, 0] * 400, 210 - np.asarray(P)[:, 1] * 400] * 4).astype(np.int32)
    for s in 'RL':
        for k in ('eye_%s_up', 'eye_%s_lo'):
            cv2.polylines(can, [T(tpl[k % s])], False, (0, 0, 0), 2, cv2.LINE_AA, shift=2)
        b = np.concatenate([tpl[f'brow_{s}_up'], tpl[f'brow_{s}_lo'][::-1]])
        cv2.fillPoly(can, [T(b)], (40, 40, 40), cv2.LINE_AA, shift=2)
        ic = tpl[f'iris_{s}']
        cv2.circle(can, (int(450 + ic[0] * 400), int(210 - ic[1] * 400)), int(ic[3] * 400), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imwrite(os.path.join(TPL, 'jade_front_debug.png'), can)
    print('template from', used, 'eye_open_template', tpl['eye_open_template'], 'real', tpl['eye_open_real'],
          'brow n', tpl['brow_R_n'], tpl['brow_L_n'])
    return tpl


_cache = {}


def load(kind='front'):
    if kind not in _cache:
        p = os.path.join(TPL, f'jade_{kind}.json')
        if kind == 'front' and not os.path.exists(p):
            build()
        _cache[kind] = json.load(open(p))
    return _cache[kind]


if __name__ == '__main__':
    if sys.argv[1:] == ['build']:
        build()
