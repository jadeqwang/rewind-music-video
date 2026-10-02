# Line extraction for the REDACTED NOCTURNE roto: clean, sparse, confident contour strokes.
#
# frame (BGR, any size) -> analysis at 960x540:
#   1. luma (Lab L), per-shot tone normalisation (brighten dark plates with a fixed per-shot gamma, so it is stable in time)
#   2. edge-preserving flattening (fast global smoother on the luma, guided by itself) -> graphic regions, no asphalt grain
#   3. Canny on the flattened luma (absolute hysteresis thresholds) gated by an XDoG-style band-pass strength
#   4. stroke graph: thin, split at junctions, trace 8-connected paths, drop short / weak / speckle paths,
#      bridge small gaps between path ends that point at each other
#   5. smooth each path (resample + Gaussian along the arc) and draw it at 1920x1080 (4x supersampled, then area-downsampled)
#      with a near-constant weight: strong edges ~3 px, weak ~2 px, tapered ends (hand-inked look)
# Suppression masks (ground/grass, face) are applied before tracing, so suppressed regions produce no strokes at all.
import cv2, numpy as np

AW, AH = 960, 540          # analysis size
OW, OH = 1920, 1080        # output size
SS = 4                     # supersample for drawing
X = cv2.ximgproc

DEFAULTS = dict(
    gamma=None,            # per-shot gamma (None -> from shot stats)
    clahe=1.6,             # CLAHE clip (0 = off)
    fgs_lambda=220.0, fgs_sigma=7.0,   # fast global smoother strength (flattening)
    canny_lo=14, canny_hi=34,          # on the flattened 0..255 luma
    min_len=34,            # min path length (analysis px) for an isolated path
    min_len_closed=60,     # closed loops (blobs: window dots, specks) need a larger perimeter
    min_strength=0.10,     # min mean band-pass strength along the path
    density_r=10, density_max=0.20,  # local stroke density (texture) suppression
    min_lin=0.035,         # min gradient in LINEAR luma (before the gamma lift): kills lifted compression blotches
    max_wiggle=0.10,       # max mean turning (rad/px) of the smoothed path for weak paths (noise wiggles)
    w_min=1.7, w_max=3.2,  # stroke width range at 1080p (px)
    taper=14.0,            # taper length at 1080p (px)
    smooth=2.2,            # Gaussian sigma along the path (analysis px)
    gap=7,                 # bridge end-to-end gaps up to this (analysis px)
)


def shot_tone(frames_gray):
    """Per-shot tone params from a few sample luma frames (uint8). Returns gamma mapping p995 -> 1 and lifting the
    mid-dark range so that the 70th percentile lands near 0.33."""
    v = np.concatenate([f.ravel()[::7] for f in frames_gray]).astype(np.float32) / 255
    hi = max(0.25, float(np.percentile(v, 99.5)))
    p70 = max(0.01, float(np.percentile(v, 70))) / hi
    gamma = float(np.clip(np.log(0.33) / np.log(min(0.9, p70)), 0.35, 1.0))
    return dict(hi=hi, gamma=gamma)


def tone(gray, tn, clahe=1.6):
    g = np.clip(gray.astype(np.float32) / 255 / tn['hi'], 0, 1) ** tn['gamma']
    g8 = (g * 255).astype(np.uint8)
    if clahe:
        g8 = cv2.createCLAHE(clipLimit=clahe, tileGridSize=(6, 6)).apply(g8)
    return g8


def flatten(g8, p):
    return X.fastGlobalSmootherFilter(g8, g8, p['fgs_lambda'], p['fgs_sigma'])


def bandpass(f8):
    f = f8.astype(np.float32) / 255
    d = cv2.GaussianBlur(f, (0, 0), 1.0) - cv2.GaussianBlur(f, (0, 0), 2.4)
    gx = cv2.Sobel(cv2.GaussianBlur(f, (0, 0), 1.0), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(cv2.GaussianBlur(f, (0, 0), 1.0), cv2.CV_32F, 0, 1, ksize=3)
    gm = np.sqrt(gx * gx + gy * gy)
    return np.clip(np.maximum(np.abs(d) * 9.0, gm * 1.6), 0, 1)


N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def trace(skel):
    """Split a 1-px skeleton into simple paths. Returns list of (N,2) int arrays of (y,x) and a closed flag."""
    sk = (skel > 0).astype(np.uint8)
    # crossing number (0->1 transitions around the 8-neighbourhood): >= 3 is a real junction; staircase pixels
    # with 3 neighbours on a diagonal curve have 2 transitions and stay on the path
    pd = np.pad(sk, 1)
    H_, W_ = sk.shape
    ring = [pd[0:H_, 1:W_ + 1], pd[0:H_, 2:W_ + 2], pd[1:H_ + 1, 2:W_ + 2], pd[2:H_ + 2, 2:W_ + 2],
            pd[2:H_ + 2, 1:W_ + 1], pd[2:H_ + 2, 0:W_], pd[1:H_ + 1, 0:W_], pd[0:H_, 0:W_]]
    cn = np.zeros(sk.shape, np.int32)
    for k in range(8):
        cn += ((ring[k] == 0) & (ring[(k + 1) % 8] == 1))
    junc = (cn >= 3) & (sk > 0)
    body = (sk > 0) & ~junc
    n, lab = cv2.connectedComponents(body.astype(np.uint8), connectivity=8)
    if n <= 1:
        return []
    ys, xs = np.nonzero(body)
    ls = lab[ys, xs]
    order = np.argsort(ls, kind='stable')
    ys, xs, ls = ys[order], xs[order], ls[order]
    starts = np.searchsorted(ls, np.arange(1, n))
    ends = np.append(starts[1:], len(ls))
    H, W = sk.shape
    jy, jx = np.nonzero(junc)
    jset = set(zip(jy.tolist(), jx.tolist()))
    paths = []
    bodyset_lab = lab
    for k in range(n - 1):
        s, e = starts[k], ends[k]
        if e - s < 3:
            continue
        pts = set(zip(ys[s:e].tolist(), xs[s:e].tolist()))
        lbl = k + 1
        # endpoints: pixels with exactly one neighbour inside the component
        def nbrs(p):
            y, x = p
            return [(y + dy, x + dx) for dy, dx in N8 if (y + dy, x + dx) in pts]
        start = None
        for p in pts:
            if len(nbrs(p)) == 1:
                start = p; break
        closed = start is None
        if closed:
            start = next(iter(pts))
        path = [start]; seen = {start}; cur = start
        while True:
            nx = [q for q in nbrs(cur) if q not in seen]
            if not nx:
                break
            # prefer 4-neighbours (keeps the walk on the curve)
            nx.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            cur = nx[0]; seen.add(cur); path.append(cur)
        if len(path) < 3:
            continue
        # re-attach junction pixels next to the ends so strokes meet at junctions
        for idx in (0, -1):
            y, x = path[idx]
            for dy, dx in N8:
                q = (y + dy, x + dx)
                if q in jset:
                    if idx == 0: path.insert(0, q)
                    else: path.append(q)
                    break
        paths.append((np.array(path, np.int32), closed))
    return paths


def arclen(P):
    d = np.diff(P.astype(np.float32), axis=0)
    return float(np.sqrt((d * d).sum(1)).sum())


def smooth_path(P, sigma, closed):
    """Resample to ~1 px steps and Gaussian-smooth along the arc (keeps the ends fixed for open paths)."""
    P = P[:, ::-1].astype(np.float32)  # -> (x,y)
    if len(P) < 4 or sigma <= 0:
        return P
    k = int(3 * sigma + 0.5); w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma) ** 2); w /= w.sum()
    if closed:
        Q = np.concatenate([P[-k:], P, P[:k]])
        out = np.stack([np.convolve(Q[:, i], w, 'valid') for i in range(2)], 1)
        return np.concatenate([out, out[:1]])
    Q = np.concatenate([np.repeat(P[:1], k, 0), P, np.repeat(P[-1:], k, 0)])
    out = np.stack([np.convolve(Q[:, i], w, 'valid') for i in range(2)], 1)
    out[0], out[-1] = P[0], P[-1]
    return out


def wiggle(Q):
    if len(Q) < 5:
        return 0.0
    d = np.diff(Q[::2], axis=0); a = np.arctan2(d[:, 1], d[:, 0])
    da = np.abs((np.diff(a) + np.pi) % (2 * np.pi) - np.pi)
    return float(da.sum() / max(1.0, arclen(Q)))


def bridge(paths, gap):
    """Join open path ends that are close and roughly collinear (closes small gaps in contours)."""
    if gap <= 0 or len(paths) < 2:
        return paths
    ends = []
    for i, (P, closed) in enumerate(paths):
        if closed or len(P) < 6:
            continue
        for side in (0, 1):
            a = P[0] if side == 0 else P[-1]
            b = P[min(5, len(P) - 1)] if side == 0 else P[max(0, len(P) - 6)]
            d = (a - b).astype(np.float32); d /= (np.linalg.norm(d) + 1e-6)
            ends.append((i, side, a.astype(np.float32), d))
    if len(ends) < 2:
        return paths
    E = np.array([e[2] for e in ends]); D = np.array([e[3] for e in ends])
    used = set(); links = []
    dist = np.sqrt(((E[:, None] - E[None]) ** 2).sum(-1))
    for a in range(len(ends)):
        for b in np.argsort(dist[a])[1:4]:
            if dist[a, b] > gap or ends[a][0] == ends[b][0]:
                continue
            if a in used or b in used:
                continue
            v = (E[b] - E[a]) / (dist[a, b] + 1e-6)
            if np.dot(D[a], v) > 0.5 and np.dot(D[b], -v) > 0.5:
                used.add(a); used.add(b); links.append((E[a], E[b]))
    out = list(paths)
    for pa, pb in links:   # a bridge is a tiny straight path (drawn with the same weight)
        n = max(2, int(np.linalg.norm(pb - pa)) + 1)
        seg = np.round(np.linspace(pa, pb, n)).astype(np.int32)
        out.append((seg, False))
    return out


def pointlight_mask(lin, thr=0.8, max_frac=0.012):
    """Small bright cores (streetlamps, headlights, siren bulbs) and their bloom: no strokes there (the light layer
    carries them; halo rings drawn as lines look like edge-detector noise). Big bright areas (screens, windows) keep lines."""
    core = (lin > thr).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(core, connectivity=8)
    m = np.zeros_like(core)
    A = core.size
    for i in range(1, n):
        a = st[i, 4]; bw, bh = st[i, 2], st[i, 3]
        if a > max_frac * A or max(bw, bh) > 2.2 * min(bw, bh) + 4 or a < 0.45 * bw * bh:
            continue   # only compact round cores (lamps, bulbs), not streaks / lit road / rims
        r = int(min(22, 1.8 * np.sqrt(a / np.pi) + 6))
        cv2.circle(m, (int(cen[i][0]), int(cen[i][1])), r, 1, -1)
    return m


def skyline_mask(lin):
    """Distant skylines / window dots: zones dense with tiny isolated bright points (top-hat blobs no bigger than
    ~5 px, so poles / lane lines / rims are not dots). No strokes there."""
    th = lin - cv2.morphologyEx(lin, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    b = (th > 0.08).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(b, connectivity=8)
    small = (st[:, 2] <= 6) & (st[:, 3] <= 6) & (st[:, 4] <= 24)
    small[0] = False
    dots = np.zeros(lin.shape, np.float32)
    c = cen[small].astype(np.int32)
    dots[np.clip(c[:, 1], 0, lin.shape[0] - 1), np.clip(c[:, 0], 0, lin.shape[1] - 1)] = 1
    d = cv2.blur(dots, (61, 25))
    z = (d > 7.0 / (61 * 25)).astype(np.uint8)          # >= ~7 dots in a 61x25 window
    n, lab, st, _ = cv2.connectedComponentsWithStats(z)
    m = np.zeros_like(z)
    for i in range(1, n):
        if st[i, 4] > 1500 and st[i, 2] > 2.5 * st[i, 3]:   # skylines are wide horizontal bands
            m[lab == i] = 1
    return cv2.dilate(m, np.ones((5, 5), np.uint8))


def extract(bgr, tn, p=None, suppress=None, return_debug=False):
    """bgr: frame (any size). tn: shot tone params. suppress: float mask at AWxAH (1 = no lines).
    Returns float32 alpha (OH,OW) in 0..1, plus stats."""
    p = {**DEFAULTS, **(p or {})}
    a = cv2.resize(bgr, (AW, AH), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(a, cv2.COLOR_BGR2LAB)[..., 0]
    g8 = tone(gray, tn, p['clahe'])
    f8 = flatten(g8, p)
    strength = bandpass(f8)
    lin = cv2.GaussianBlur(np.clip(gray.astype(np.float32) / 255 / tn['hi'], 0, 1), (0, 0), 1.2)
    lgm = np.sqrt(cv2.Sobel(lin, cv2.CV_32F, 1, 0, ksize=3) ** 2 + cv2.Sobel(lin, cv2.CV_32F, 0, 1, ksize=3) ** 2)
    lgm = cv2.dilate(lgm, np.ones((3, 3), np.uint8))
    ed = cv2.Canny(f8, p['canny_lo'], p['canny_hi'], L2gradient=True)
    if p.get('pointlights', True):
        ed[pointlight_mask(lin) > 0] = 0
    if suppress is not None:
        ed[suppress > 0.5] = 0
    if p.get('skyline', True):
        sky = skyline_mask(lin)
        ed[sky > 0] = 0
    else:
        sky = None
    sk = X.thinning(ed)
    paths = trace(sk)
    # coarse pass (480x270, extra smoothing): soft big boundaries (road edges in glow, dark car on dark road, mirror rims)
    if p.get('coarse', True):
        c8 = cv2.resize(f8, (AW // 2, AH // 2), interpolation=cv2.INTER_AREA)
        c8 = X.fastGlobalSmootherFilter(c8, c8, p['fgs_lambda'] * 0.5, p['fgs_sigma'])
        ce = cv2.Canny(c8, p['canny_lo'] * 0.8, p['canny_hi'] * 0.8, L2gradient=True)
        sup = cv2.dilate(sk, np.ones((7, 7), np.uint8))   # already covered by fine strokes
        sup = cv2.resize(sup, (AW // 2, AH // 2), interpolation=cv2.INTER_NEAREST)
        if suppress is not None:
            sup = np.maximum(sup, (cv2.resize(suppress, (AW // 2, AH // 2)) > 0.5).astype(np.uint8))
        if sky is not None:
            sup = np.maximum(sup, cv2.resize(sky, (AW // 2, AH // 2), interpolation=cv2.INTER_NEAREST))
        pl = cv2.resize(pointlight_mask(lin), (AW // 2, AH // 2), interpolation=cv2.INTER_NEAREST)
        ce[(sup > 0) | (pl > 0)] = 0
        for P, closed in trace(X.thinning(ce)):
            if arclen(P) >= p['min_len'] * 0.75:
                paths.append((P * 2, closed))
    # texture density (fraction of stroke pixels in a window): high-density areas are speckle/texture
    r = p['density_r']
    dens = cv2.blur((sk > 0).astype(np.float32), (2 * r + 1, 2 * r + 1))
    keep = []
    for P, closed in paths:
        L = arclen(P)
        need = p['min_len_closed'] if closed else p['min_len']
        if L < need:
            continue
        st = float(strength[P[:, 0], P[:, 1]].mean())
        if st < p['min_strength']:
            continue
        if float(lgm[P[:, 0], P[:, 1]].mean()) < p['min_lin']:
            continue
        if st < 0.45 and wiggle(smooth_path(P, p['smooth'], closed)) > p['max_wiggle']:
            continue
        dn = float(dens[P[:, 0], P[:, 1]].mean())
        if dn > p['density_max'] and L < 4 * need:
            continue
        keep.append((P, closed, st, L))
    br = bridge([(P, c) for P, c, _, _ in keep], p['gap'])
    strokes = []
    for i, (P, closed) in enumerate(br):
        st = keep[i][2] if i < len(keep) else 0.5
        strokes.append((smooth_path(P, p['smooth'], closed), closed, st))
    alpha = draw(strokes, p)
    if return_debug:
        return alpha, dict(g8=g8, f8=f8, edges=ed, strength=strength, n=len(strokes))
    return alpha, dict(n=len(strokes))


def draw(strokes, p):
    """Draw smoothed strokes at OWxOH: 4x supersampled canvas, width from strength, tapered ends."""
    S = SS * OW / AW
    can = np.zeros((OH * SS, OW * SS), np.uint8)
    taper = p['taper'] * SS
    for Q, closed, st in strokes:
        if len(Q) < 2:
            continue
        w = p['w_min'] + (p['w_max'] - p['w_min']) * float(np.clip((st - 0.1) / 0.5, 0, 1))
        pts = Q * S
        seg = np.sqrt((np.diff(pts, axis=0) ** 2).sum(1)); s = np.concatenate([[0], np.cumsum(seg)]); Ltot = s[-1]
        if closed:
            tw = np.ones_like(s)
        else:
            tw = np.clip(np.minimum(s, Ltot - s) / max(1.0, min(taper, Ltot / 2)), 0, 1) ** 0.6
            tw = 0.35 + 0.65 * tw
        th = np.maximum(1, np.round(w * SS * tw)).astype(np.int32)
        P = np.round(pts * 4).astype(np.int32)   # cv2 shift=2 sub-pixel
        # draw runs of constant thickness as polylines
        i0 = 0
        for i in range(1, len(P) + 1):
            if i == len(P) or th[i] != th[i0]:
                run = P[max(0, i0 - 1):i]
                if len(run) >= 2:
                    cv2.polylines(can, [run], False, 255, int(th[i0]), cv2.LINE_AA, shift=2)
                i0 = i
    out = cv2.resize(can, (OW, OH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return np.clip(out * 1.15, 0, 1)
