# Jade drawing v2: 3-tone cel layer (ink / mid / bone) per roto frame, with the FACE SHAPE from her real-photo template,
# designed HAIR (centre part, half-up crown pieces, flat ink mass + crisp mid-tone strands) and crisp spline edges.
# Writes assets/roto/<J>/cel/NNNN.png (RGBA 1920x1080, final palette colours, alpha = figure) and assets/roto/<J>/cel.json
# (per frame: lips {outer, inner, c, w}, irises [[x,y,r]], glasses {front: lenses | profile: lens quad + arm}).
#   python3 tools/jade2/build.py J6 [J1 ...] [--frames 0:20] [--every 1]
import os, sys, json, math, numpy as np, cv2
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')
INK, MID, BONE = (10, 8, 7), (138, 149, 156), (216, 230, 236)          # BGR: #07080A-ish, #9C958A, #ECE6D8
MID_FACE = (170, 180, 188)                                               # lighter mid for skin shadow (warm)
HAIR_STRAND = (62, 64, 68)
W, H = 1920, 1080
SH = json.load(open(ROOT + '/tools/jade2/jade_shape.json'))
TF = json.load(open(ROOT + '/tools/roto/templates/jade_front.json'))
# MediaPipe's oval stops at the upper forehead; her real forehead / upper head is larger: lift the upper oval (rounded)
LIFT, LOWER, CHEEK = 1.48, 0.93, 1.07
_ny = SH['nose_tip'][1]
def _shape(P):
    P = np.array(P, np.float64)
    y = P[:, 1]
    P[:, 1] = np.where(y > 0, y * LIFT, np.where(y < _ny, _ny + (y - _ny) * LOWER, y))          # big forehead, shorter lower face
    w = np.exp(-((y + 0.25) / 0.55) ** 2)                                                          # full cheeks/cheekbones, taper in the lower third
    P[:, 0] = P[:, 0] * (1 + (CHEEK - 1) * w)
    return P.tolist()
SH['oval'] = _shape(SH['oval']); SH['forehead'] = _shape([SH['forehead']])[0]
SH['lips_outer'] = _shape(SH['lips_outer']); SH['lips_inner'] = _shape(SH['lips_inner']); SH['chin'] = _shape([SH['chin']])[0]
PS = json.load(open(ROOT + '/tools/jade2/jade_profile_shape.json'))
ORANGE = (15, 134, 232)

def chaikin(P, it=3):
    P = np.asarray(P, np.float32)
    for _ in range(it):
        Q = np.roll(P, -1, 0); P = np.stack([0.75 * P + 0.25 * Q, 0.25 * P + 0.75 * Q], 1).reshape(-1, 2)
    return P

def smooth_fill(mask, val, out, min_area=600, step=6, it=3, holes=True):
    """binary mask -> spline-smoothed filled regions painted into out (respecting holes)."""
    cs, hier = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None: return out
    hier = hier[0]
    for i, c in enumerate(cs):
        if hier[i][3] != -1: continue
        if cv2.contourArea(c) < min_area: continue
        p = c[::step, 0, :].astype(np.float32)
        if len(p) < 4: continue
        cv2.fillPoly(out, [np.round(chaikin(p, it) * 4).astype(np.int32)], val, cv2.LINE_AA, shift=2)
        if holes:
            j = hier[i][2]
            while j != -1:
                if cv2.contourArea(cs[j]) > min_area:
                    q = cs[j][::step, 0, :].astype(np.float32)
                    if len(q) >= 4: cv2.fillPoly(out, [np.round(chaikin(q, it) * 4).astype(np.int32)], 0 if out.ndim == 2 else (0, 0, 0, 0) if out.shape[2] == 4 else (0, 0, 0), cv2.LINE_AA, shift=2)
                j = hier[j][0]
    return out

def alpha(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None: return None
    return (im[..., 3] if im.ndim == 3 and im.shape[2] == 4 else im if im.ndim == 2 else im[..., 0]).astype(np.float32) / 255

def rot_y(P, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
    return np.stack([c * X + s * Z, Y, -s * X + c * Z], 1)

def fit_sim(src, dst):
    M, _ = cv2.estimateAffinePartial2D(np.float32(src), np.float32(dst))
    return M

def apply(M, P): P = np.asarray(P, np.float64); return P @ M[:, :2].T + M[:, 2]

def front_geom(fd):
    eR = np.array(fd['eye_R_upper'] + fd['eye_R_lower']); eL = np.array(fd['eye_L_upper'] + fd['eye_L_lower'])
    if eR[:, 0].mean() > eL[:, 0].mean(): eR, eL = eL, eR
    cR = eR[np.argmin(eR[:, 0])]; cL = eL[np.argmax(eL[:, 0])]               # outer canthi (image left / right)
    yaw = float(fd.get('yaw', 0))
    def proj(P3):
        P = rot_y(np.asarray(P3, np.float64), -yaw); return np.c_[P[:, 0], -P[:, 1]]   # y down
    can = proj([[-0.5, 0, 0], [0.5, 0, 0]])
    # template canthi (−0.5 = her right = image left)
    a, b = can[0], can[1]; vs, vd = b - a, cL - cR
    s_ = np.linalg.norm(vd) / max(1e-6, np.linalg.norm(vs)); th = math.atan2(vd[1], vd[0]) - math.atan2(vs[1], vs[0])
    R2 = s_ * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    M = np.c_[R2, cR - R2 @ a]
    return M, proj, np.linalg.norm(cL - cR), yaw

def build_frame(J, i, frame, meta, fd, pf):
    d = f'{ROOT}/assets/roto/{J}'
    mt = alpha(f'{d}/matte/{i:04d}.png'); hr = alpha(f'{d}/hair/{i:04d}.png'); fm = alpha(f'{d}/face/{i:04d}.png')
    out = np.zeros((H, W, 4), np.uint8); info = {}
    fig = (cv2.GaussianBlur(mt, (0, 0), 3) > 0.5)
    lum = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(frame, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    for _ in range(3): small = cv2.bilateralFilter(small, 9, 40, 9)
    sl = cv2.medianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 9)
    L = cv2.resize(sl, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    mode = (fd or {}).get('mode', 'front')
    face = np.zeros((H, W), np.uint8); hair = (cv2.GaussianBlur(hr, (0, 0), 4) > 0.45).astype(np.uint8) if hr is not None else np.zeros((H, W), np.uint8)
    iod = 150
    face_ft = (cv2.GaussianBlur(fm, (0, 0), 3) > 0.5).astype(np.uint8) if fm is not None else np.zeros((H, W), np.uint8)
    if fd and mode != 'profile' and 'eye_R_upper' in fd:
        M, proj, iod, yaw = front_geom(fd)
        info['_canthi'] = apply(M, proj([[-0.5, 0, 0], [0.5, 0, 0]])).tolist(); info['chin'] = apply(M, proj([SH['chin']]))[0].round(1).tolist()
        oval = apply(M, proj(SH['oval']))
        cv2.fillPoly(face, [np.round(chaikin(oval, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        top = apply(M, proj([SH['forehead']]))[0]
        inner = cv2.erode(face, np.ones((int(iod * 0.16) | 1, int(iod * 0.16) | 1), np.uint8)); hair[inner > 0] = 0   # hair may overlap the cheek edges, never the face centre
        # hairline: centre part a little below the oval top, curving down to the temples (large forehead stays visible)
        ovp = np.array(proj(SH['oval'])); ov = apply(M, ovp)
        templeL = ov[np.argmin(np.abs(ovp[:, 1] + 0.85) + (ovp[:, 0] > 0) * 9)]; templeR = ov[np.argmin(np.abs(ovp[:, 1] + 0.85) + (ovp[:, 0] < 0) * 9)]
        part = apply(M, proj([[0.05, 1.12, 0.2]]))[0]
        up = (top - (templeL + templeR) / 2); up /= max(1e-6, np.linalg.norm(up))
        crown = []
        # hair cap over the forehead top: two curtains from the part to each temple
        for side, tp in ((-1, templeL), (1, templeR)):
            ctrl = part + (tp - part) * 0.5 + up * iod * 0.10
            curve = [part + (tp - part) * t * t * 0 + (1 - t) ** 2 * (part - part) + 2 * (1 - t) * t * (ctrl - part) + t * t * (tp - part) for t in np.linspace(0, 1, 16)]
            cap = np.array(curve + [tp + (tp - part) * 0.12 - up * iod * 0.05, tp + up * iod * 0.8 + (tp - part) * 0.25, part + up * iod * 0.9])
            cv2.fillPoly(hair, [np.round(chaikin(cap, 2) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        # half-up: two symmetrical gathered pieces toward the crown (fuller crown silhouette)
        perp = np.array([up[1], -up[0]])
        for side in (-1, 1):
            c = top + up * iod * 0.30 + perp * side * iod * 0.30
            cv2.ellipse(hair, (int(c[0]), int(c[1])), (int(iod * 0.42), int(iod * 0.30)), math.degrees(math.atan2(up[1], up[0])) + 90 + side * 18, 0, 360, 1, -1, cv2.LINE_AA)
        info['part'] = part.round(1).tolist(); info['crown'] = (top + up * iod * 0.3).round(1).tolist(); info['top'] = top.round(1).tolist(); info['up'] = up.round(4).tolist(); info['iod'] = float(iod)
        # lips template, centred on the footage mouth
        lo = apply(M, proj(SH['lips_outer'])); li = apply(M, proj(SH['lips_inner']))
        if fd.get('lips'):
            fl = np.array(fd['lips']); dlt = fl.mean(0) - lo.mean(0); dlt[1] = 0; lo += dlt; li += dlt
        info['lips'] = dict(outer=lo.round(1).tolist(), inner=li.round(1).tolist())
        info['iris'] = [fd[k] for k in ('eye_R_iris', 'eye_L_iris') if k in fd]
        info['glasses'] = dict(kind='front')
        info['nose'] = apply(M, proj([SH['nose_tip']]))[0].round(1).tolist()
    else:
        if fd and 'E' in fd:   # glasses rims read as 'hair' near the eye: drop footage hair within ~0.7·|EN| of the eye
            E0, N0 = np.array(fd['E']), np.array(fd['N']); cv2.circle(hair, (int(E0[0]), int(E0[1])), int(np.linalg.norm(N0 - E0) * 0.75), 0, -1)
        face = cv2.morphologyEx(face_ft & (1 - hair), cv2.MORPH_OPEN, np.ones((25, 25), np.uint8))
        if fd and 'E' in fd:
            E, N = np.array(fd['E']), np.array(fd['N']); dd = np.linalg.norm(N - E); iod = dd * 1.6
            back = np.sign(E[0] - N[0]) or 1.0
            # hand-annotated profile template (her real photo) mapped E,N -> E,N (similarity); mirror if she faces right
            tE, tN = np.array(PS['E'], float), np.array(PS['N'], float)
            def T(P):
                P = np.array(P, float)
                if back < 0: P[:, 0] = 2 * tE[0] - P[:, 0]; tN_ = np.array([2 * tE[0] - tN[0], tN[1]])
                else: tN_ = tN
                vs, vd = tN_ - tE, N - E; sc_ = np.linalg.norm(vd) / np.linalg.norm(vs); th = math.atan2(vd[1], vd[0]) - math.atan2(vs[1], vs[0])
                R2 = sc_ * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
                return (P - tE) @ R2.T + E
            sil, hl, sk = T(PS['silhouette']), T(PS['hairline']), T(PS['skull'])
            # skin: profile curve + hairline (front→back) + down behind the jaw
            skin_poly = np.vstack([sil, sil[-1:] + [back * dd * 0.6, 0], hl[::-1]])
            face = np.zeros((H, W), np.uint8); cv2.fillPoly(face, [np.round(chaikin(skin_poly, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
            # hair: skull cap above the hairline + the footage hair mass behind
            cap = np.vstack([hl, sk[::-1]])
            hair[face > 0] = 0
            cv2.fillPoly(hair, [np.round(chaikin(cap, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
            crown = T([[1700, 260]])[0]
            cv2.ellipse(hair, (int(crown[0]), int(crown[1])), (int(dd * 0.9), int(dd * 0.55)), -15 * back, 0, 360, 1, -1, cv2.LINE_AA)
            lens, arm = T(PS['lens']), T(PS['arm'])
            c0 = lens.mean(0); lens = c0 + (lens - c0) * np.array([0.55, 1.0])   # slimmer: the footage is closer to true profile
            info['glasses'] = dict(kind='profile', lens=lens.round(1).tolist(), arm=[(c0 + (np.array(T([PS['arm'][0]])[0]) - c0) * np.array([0.55, 1])).round(1).tolist(), arm[1].round(1).tolist()])
            info['iris'] = [fd['eye_near_iris']] if 'eye_near_iris' in fd else []
            info['crown'] = crown.round(1).tolist(); info['E'] = E.tolist(); info['N'] = N.tolist(); info['back'] = float(back)
            info['nostril'] = T([PS['nostril']])[0].round(1).tolist(); info['mouth_corner'] = T([PS['mouth_corner']])[0].round(1).tolist()
            info['sil'] = sil.round(1).tolist()
            # nothing of the footage figure may stick out in front of her real profile curve (forehead → chin)
            chin_i = int(np.argmax(sil[:, 1] * 0 + np.arange(len(sil)) == 15))
            front = np.vstack([sil[:16], [sil[15][0] - back * dd * 4, sil[15][1]], [sil[0][0] - back * dd * 4, sil[0][1] - dd * 2], [sil[0][0], sil[0][1] - dd * 2]])
            info['_front'] = front
        info['mouth'] = pf.get('mouth')
    # dark regions of the upper figure are hair (the roto hair mask misses the front of the head)
    eye_y = (info['E'][1] if 'E' in info else (np.mean([p[1] for p in info.get('iris', [[0, 540]])]) if info.get('iris') else 540))
    fv = L[fig]; dark = fig & (L < (np.percentile(fv, 30) if fv.size else 0)) & (np.arange(H)[:, None] < eye_y + iod * 0.9) & (face == 0)
    dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, np.ones((11, 11), np.uint8))
    hair = hair | (dark & (1 - face))
    if False:   # (v2 hack, superseded by the profile template)
        top = fig & (L < np.percentile(L[face > 0], 35)) & (np.arange(H)[:, None] < info['E'][1] - iod * 0.25)
        top = cv2.morphologyEx(top.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        E0 = np.array(info['E']); cv2.circle(top, (int(E0[0]), int(E0[1])), int(iod / 1.6 * 0.9), 0, -1)
        hair = hair | top; face = face & (1 - top)
    hair_designed = hair.copy()
    if '_front' in info:
        fr_ = np.zeros((H, W), np.uint8); cv2.fillPoly(fr_, [np.round(info.pop('_front') * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        fig = fig & (fr_ == 0); hair_designed = hair_designed & (1 - fr_)
    figure = (fig.astype(np.uint8) | face | hair_designed) > 0
    # ---- outfit as designed shapes: bone jacket, her orange bands (from the footage hue, cleaned), black top (ink),
    #      at most 2 large mid-tone fold shadows
    body = figure & (face == 0) & (hair_designed == 0)
    figure = cv2.morphologyEx(figure.astype(np.uint8), cv2.MORPH_OPEN, np.ones((15, 15), np.uint8)) > 0
    smooth_fill(figure, (*BONE, 255), out, min_area=6000, step=7, it=4)
    if body.sum() > 1000:
        hsv = cv2.cvtColor(cv2.resize(small, (W, H)), cv2.COLOR_BGR2HSV); hh_, ss_, vv_ = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        orange = body & (hh_ >= 4) & (hh_ <= 19) & (ss_ > 140) & (vv_ > 90)
        v = L[body]; t_dark, t_mid = np.percentile(v, 12), np.percentile(v, 40)
        ink = body & (L < t_dark) & ~orange
        mid = body & (L >= t_dark) & (L < t_mid) & ~orange
        k = np.ones((13, 13), np.uint8)
        mid = cv2.morphologyEx(cv2.morphologyEx(mid.astype(np.uint8), cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)
        n, lab, st, _ = cv2.connectedComponentsWithStats(mid)
        keep = np.zeros(n, bool); order = np.argsort(-st[1:, 4]) + 1; keep[order[:2]] = True; keep[0] = False
        mid = keep[lab].astype(np.uint8) & body
        smooth_fill(mid, (*MID, 255), out, min_area=6000, step=8, it=4, holes=False)
        orange = cv2.morphologyEx(cv2.morphologyEx(orange.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)) & body
        smooth_fill(orange, (*ORANGE, 255), out, min_area=4000, step=8, it=4, holes=False)
        ink = cv2.morphologyEx(cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k) & body
        smooth_fill(ink, (*INK, 255), out, min_area=9000, step=8, it=4, holes=False)
    # ---- face: 2 tones max, large smooth shadow shapes only near the edge (cheekbone / jaw) — never under the eyes
    if face.sum() > 500:
        fl = cv2.GaussianBlur(L, (0, 0), 14)
        fv = fl[face > 0]; thr = np.percentile(fv, 14)
        dist = cv2.distanceTransform(face, cv2.DIST_L2, 5)
        sh = (face > 0) & (fl < thr) & (dist < iod * 0.13)
        for ir in info.get('iris', []) or []:
            cv2.circle(sh.view(np.uint8), (int(ir[0]), int(ir[1])), int(iod * 0.42), 0, -1)
        sh = cv2.morphologyEx(sh.astype(np.uint8), cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
        smooth_fill(face, (*BONE, 255), out, min_area=500, step=10 if 'E' in info else 4, it=4)
        smooth_fill(sh, (*MID_FACE, 255), out, min_area=int(face.sum() * 0.03), step=8, it=4, holes=False)
        # under-jaw shadow on the neck
        if 'nose' in info:
            jaw = np.zeros((H, W), np.uint8); cv2.fillPoly(jaw, [np.round(chaikin(oval, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
            sj = cv2.dilate(jaw, np.ones((1, 1), np.uint8)); shifted = np.zeros_like(jaw); dy = int(iod * 0.16); shifted[dy:] = jaw[:-dy]
            neck = (shifted > 0) & (jaw == 0) & body
            smooth_fill(neck.astype(np.uint8), (*MID, 255), out, min_area=400, step=5, it=3, holes=False)
    # face contour (drawn before the hair so hair overlaps it): thin warm-dark line on the lower face (cheek → chin), where it borders bone
    if 'nose' in info:
        ovs = chaikin(oval, 3); ny = np.array(info['nose'])[1] + iod * 0.12
        low = ovs[:, 1] > ny; idx = np.where(low)[0]
        if len(idx) > 4:
            # rotate so the arc is contiguous
            start = next((j for j in range(len(ovs)) if low[j] and not low[j - 1]), idx[0])
            arc = [ovs[(start + k) % len(ovs)] for k in range(len(ovs)) if low[(start + k) % len(ovs)]]
            cv2.polylines(out, [np.round(np.array(arc) * 4).astype(np.int32)], False, (120, 128, 140, 255), 2, cv2.LINE_AA, shift=2)
    # ---- hair: flat ink mass + 6–12 crisp mid-tone strands following the fall
    if 'E' in info: hair_designed = cv2.morphologyEx(hair_designed.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    smooth_fill(hair_designed, (*INK, 255), out, min_area=1500, step=9 if 'E' in info else 5, it=4)
    strands = np.zeros((H, W), np.uint8)
    if 'part' in info:
        part, up, iod_ = np.array(info['part']), np.array(info['up']), info['iod']; perp = np.array([up[1], -up[0]])
        R0 = np.random.default_rng(7)   # static design (same every frame)
        for side in (-1, 1):
            for k_ in range(4):
                off = 0.15 + 0.22 * k_ + R0.uniform(-0.06, 0.08); ln = R0.uniform(2.6, 4.4); bend = R0.uniform(-0.12, 0.12)
                pts = [part + perp * side * iod_ * 0.04 * k_, part + perp * side * iod_ * (0.5 + off * 0.4) + up * iod_ * (0.06 - 0.02 * k_),
                       part + perp * side * iod_ * (0.92 + off * 0.5 + bend) - up * iod_ * 0.6, part + perp * side * iod_ * (1.0 + off * 0.55 - bend) - up * iod_ * (ln * 0.5),
                       part + perp * side * iod_ * (0.95 + off * 0.6 + bend * 2) - up * iod_ * ln]
                cv2.polylines(strands, [np.round(chaikin(np.array(pts), 3)[:-6] * 4).astype(np.int32)], False, 1, 2, cv2.LINE_AA, shift=2)
        # parting shadow between the two gathered crown pieces + their gather lines
        top_ = np.array(info['top'])
        cv2.polylines(strands, [np.round(chaikin(np.array([part, top_ + up * iod_ * 0.12, top_ + up * iod_ * 0.55]), 3) * 4).astype(np.int32)], False, 1, 3, cv2.LINE_AA, shift=2)
        for side in (-1, 1):
            c = top_ + up * iod_ * 0.30 + perp * side * iod_ * 0.30
            for r in (0.62, 0.85):
                a0 = math.degrees(math.atan2(up[1], up[0]))
                cv2.ellipse(strands, (int(c[0]), int(c[1])), (int(iod_ * 0.42 * r), int(iod_ * 0.30 * r)), a0 + 90 + side * 18, 200 if side < 0 else -20, 340 if side < 0 else 120, 1, 2, cv2.LINE_AA)
    elif 'crown' in info and 'E' in info:
        E, back = np.array(info['E']), info['back']; dd = np.linalg.norm(np.array(info['N']) - E); cr = np.array(info['crown'])
        for k_ in range(5):
            a = E + np.array([-back * dd * 0.2 + back * dd * 0.25 * k_, -dd * (1.15 + 0.1 * k_)])
            pts = [a, (a + cr) / 2 + np.array([0, -dd * 0.15]), cr, cr + np.array([back * dd * 0.25, dd * (1.4 + 0.25 * k_)]), cr + np.array([back * dd * (0.1 + 0.08 * k_), dd * (3.6 + 0.2 * k_)])]
            cv2.polylines(strands, [np.round(chaikin(np.array(pts), 3) * 4).astype(np.int32)], False, 1, 2, cv2.LINE_AA, shift=2)
    sm = (strands > 0) & (out[..., :3] == INK).all(-1)
    out[sm] = (*HAIR_STRAND, 255)
    os.makedirs(f'{d}/cel', exist_ok=True)
    cv2.imwrite(f'{d}/cel/{i:04d}.png', out, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if VARIANTS and 'nose' in info:
        info['_oval'] = oval
        for v in VARIANTS: VARIANTS[v](J, i, out.copy(), frame, info, face, hair_designed, iod)
    info.pop('_oval', None); info.pop('_canthi', None)
    return info

VARIANTS = {}
SKIN, SKIN_SH, BLUSH, HAIR_HI = (182, 203, 236), (150, 172, 214), (172, 184, 236), (34, 36, 46)   # BGR warm palette
def variant_B(J, i, out, frame, info, face, hair, iod):
    """(B) 4–5 tone warm-skin cel: skin + skin shadow + cheek blush + 2-tone hair (flat shapes)."""
    fm = face > 0
    bone = (np.abs(out[..., :3].astype(int) - BONE).sum(-1) < 12) & fm
    shd = (np.abs(out[..., :3].astype(int) - MID_FACE).sum(-1) < 12) & fm
    out[bone, :3] = SKIN; out[shd, :3] = SKIN_SH
    # cheek blush: soft rose shapes on the cheekbones (flat, smooth-edged)
    lo = np.array(info['lips']['outer']); mc = lo.mean(0); nz = np.array(info['nose'])
    for side in (-1, 1):
        c = (nz[0] + side * iod * 0.42, nz[1] - iod * 0.05)
        m = np.zeros(face.shape, np.uint8); cv2.ellipse(m, (int(c[0]), int(c[1])), (int(iod * 0.17), int(iod * 0.08)), 0, 0, 360, 1, -1, cv2.LINE_AA)
        out[(m > 0) & fm & bone, :3] = BLUSH
    # hair second tone: a broad soft sheen band on the crown
    ink = (np.abs(out[..., :3].astype(int) - INK).sum(-1) < 12) & (hair > 0)
    # hair second tone: the curtains falling from the part (one lit side of each), flat shapes
    part = np.array(info['part']); up = np.array(info['up']); perp = np.array([up[1], -up[0]])
    for side in (-1, 1):
        q = np.array([part + perp * side * iod * 0.1, part + perp * side * iod * 0.55 - up * iod * 0.1, part + perp * side * iod * 0.9 - up * iod * 0.9,
                      part + perp * side * iod * 0.98 - up * iod * 2.6, part + perp * side * iod * 0.86 - up * iod * 2.6, part + perp * side * iod * 0.72 - up * iod * 0.8, part + perp * side * iod * 0.35 - up * iod * 0.05])
        m = np.zeros(face.shape, np.uint8); cv2.fillPoly(m, [np.round(chaikin(q, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        out[(m > 0) & ink, :3] = HAIR_HI
    os.makedirs(f'{ROOT}/assets/roto/{J}/celB', exist_ok=True); cv2.imwrite(f'{ROOT}/assets/roto/{J}/celB/{i:04d}.png', out)
def variant_C(J, i, out, frame, info, face, hair, iod):
    """(C) graphic portrait drawn over her REAL face: her photo warped to the frame's eye anchors, smoothed and
    posterized into 6 flat tone shapes (no photographic texture), inside the template face + hairline."""
    sys.path.insert(0, ROOT + '/tools/likeness'); import measure as MS
    ref = ROOT + '/refs/jade/IMG_20180610_074732_mr1528617091925.jpg'
    rgb = MS.load_rgb(ref); lm = MS.landmarks(rgb); P = lm[0][:, :2]
    fd_c = info['_canthi']
    src = np.float32([P[33], P[263], P[1], P[152]]); dst = np.float32([fd_c[0], fd_c[1], info['nose'], info['chin']])
    A, _ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
    warped = cv2.warpAffine(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), A, (W, H), flags=cv2.INTER_CUBIC)
    sm = warped
    for _ in range(4): sm = cv2.bilateralFilter(sm, 11, 30, 11)
    sm = cv2.medianBlur(sm, 9)
    OV = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    po = (np.c_[P[OV], np.ones(len(OV))] @ A.T)
    pm = np.zeros(face.shape, np.uint8); cv2.fillPoly(pm, [np.round(chaikin(po, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
    region = (cv2.dilate(face, np.ones((5, 5), np.uint8)) > 0) & (pm > 0)
    # her face skin inside her own face outline; outside it (forehead top / temples) keep the cel skin
    res0 = out.copy(); bone = (np.abs(res0[..., :3].astype(int) - BONE).sum(-1) < 12) & (face > 0); res0[bone, :3] = (204, 222, 244); out = res0
    px = sm[region].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lab, cen = cv2.kmeans(px, 6, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    order = np.argsort(cen.sum(1)); cen = cen[order]; remap = np.argsort(order); lab = remap[lab.ravel()]
    L = np.full(face.shape, -1, np.int32); L[region] = lab
    res = out.copy()
    for k in range(6):   # paint light → dark, each level spline-smoothed, small specks dropped
        mk = (L >= 0) & (L <= k) if False else (L >= 0) & (L >= k)
        mk = cv2.morphologyEx(mk.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        col = tuple(int(x) for x in cen[5 - k]) if False else tuple(int(x) for x in cen[k])
    # paint darkest-first-as-base: fill region with the lightest, then darker levels on top
    RAMP = [(52, 44, 58), (92, 98, 140), (124, 142, 192), (150, 172, 214), (178, 199, 233), (204, 222, 244)]   # warm skin ramp (BGR), dark → light
    smooth_fill(region.astype(np.uint8), (*RAMP[5], 255), res, min_area=500, step=4, it=3)
    for k in range(4, -1, -1):
        mk = ((L >= 0) & (L <= k)).astype(np.uint8)
        mk = cv2.morphologyEx(mk, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) & region
        smooth_fill(mk, (*RAMP[k], 255), res, min_area=int(iod * iod * 0.004), step=3, it=3, holes=False)
    os.makedirs(f'{ROOT}/assets/roto/{J}/celC', exist_ok=True); cv2.imwrite(f'{ROOT}/assets/roto/{J}/celC/{i:04d}.png', res)

def run(J, fr=None):
    d = f'{ROOT}/assets/roto/{J}'; meta = json.load(open(d + '/meta.json')); faces = json.load(open(d + '/face.json'))
    cap = cv2.VideoCapture(f"{ROOT}/{meta['src']}"); sfps = cap.get(cv2.CAP_PROP_FPS); frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    rng = range(meta['frames']) if fr is None else range(*fr)
    infos = {}
    try: infos = {int(k): v for k, v in json.load(open(d + '/cel.json'))['frames'].items()}
    except Exception: pass
    for i in rng:
        f = frames[min(len(frames) - 1, int(round((meta.get('start', 0) + i / meta['fps']) * sfps)))]
        f = cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC)
        infos[i] = build_frame(J, i, f, meta, faces[i] if i < len(faces) else None, meta['per_frame'][i])
    json.dump(dict(note='tools/jade2/build.py', frames={str(k): v for k, v in sorted(infos.items())}), open(d + '/cel.json', 'w'))
    if 'cel' not in meta['layers']: meta['layers'].append('cel'); json.dump(meta, open(d + '/meta.json', 'w'))
    print(J, len(list(rng)))

if __name__ == '__main__':
    a = sys.argv[1:]; fr = None
    if '--variants' in a: a.remove('--variants'); VARIANTS.update(B=variant_B, C=variant_C)
    if '--frames' in a: k = a.index('--frames'); fr = tuple(map(int, a[k + 1].split(':'))); a = a[:k] + a[k + 2:]
    for J in a: run(J, fr)
