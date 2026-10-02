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
_ov = np.array(SH['oval']); _ov[:, 1] = np.where(_ov[:, 1] > 0, _ov[:, 1] * 1.32, _ov[:, 1]); SH['oval'] = _ov.tolist()
SH['forehead'] = [SH['forehead'][0], SH['forehead'][1] * 1.32, SH['forehead'][2]]

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
        oval = apply(M, proj(SH['oval']))
        cv2.fillPoly(face, [np.round(chaikin(oval, 3) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        top = apply(M, proj([SH['forehead']]))[0]
        inner = cv2.erode(face, np.ones((int(iod * 0.16) | 1, int(iod * 0.16) | 1), np.uint8)); hair[inner > 0] = 0   # hair may overlap the cheek edges, never the face centre
        # hairline: centre part a little below the oval top, curving down to the temples (large forehead stays visible)
        ovp = np.array(proj(SH['oval'])); ov = apply(M, ovp)
        templeL = ov[np.argmin(np.abs(ovp[:, 1] + 0.5) + (ovp[:, 0] > 0) * 9)]; templeR = ov[np.argmin(np.abs(ovp[:, 1] + 0.5) + (ovp[:, 0] < 0) * 9)]
        part = apply(M, proj([[0.05, 0.86, 0.2]]))[0]
        up = (top - (templeL + templeR) / 2); up /= max(1e-6, np.linalg.norm(up))
        crown = []
        # hair cap over the forehead top: two curtains from the part to each temple
        for side, tp in ((-1, templeL), (1, templeR)):
            ctrl = part + (tp - part) * 0.45 + up * iod * 0.16
            curve = [part + (tp - part) * t * t * 0 + (1 - t) ** 2 * (part - part) + 2 * (1 - t) * t * (ctrl - part) + t * t * (tp - part) for t in np.linspace(0, 1, 16)]
            cap = np.array(curve + [tp + (tp - part) * 0.12 - up * iod * 0.05, tp + up * iod * 0.8 + (tp - part) * 0.25, part + up * iod * 0.9])
            cv2.fillPoly(hair, [np.round(chaikin(cap, 2) * 4).astype(np.int32)], 1, cv2.LINE_AA, shift=2)
        # half-up: two symmetrical gathered pieces toward the crown (fuller crown silhouette)
        perp = np.array([up[1], -up[0]])
        for side in (-1, 1):
            c = top + up * iod * 0.22 + perp * side * iod * 0.36
            cv2.ellipse(hair, (int(c[0]), int(c[1])), (int(iod * 0.48), int(iod * 0.34)), math.degrees(math.atan2(up[1], up[0])) + 90 + side * 18, 0, 360, 1, -1, cv2.LINE_AA)
        info['part'] = part.round(1).tolist(); info['crown'] = (top + up * iod * 0.3).round(1).tolist(); info['up'] = up.round(4).tolist(); info['iod'] = float(iod)
        # lips template, centred on the footage mouth
        lo = apply(M, proj(SH['lips_outer'])); li = apply(M, proj(SH['lips_inner']))
        if fd.get('lips'):
            fl = np.array(fd['lips']); dlt = fl.mean(0) - lo.mean(0); lo += dlt; li += dlt
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
            # half-up piece seen from the side: a gathered lobe at the back of the crown + the tie
            crown = E + np.array([back * dd * 1.25, -dd * 1.75])
            cv2.ellipse(hair, (int(crown[0]), int(crown[1])), (int(dd * 0.95), int(dd * 0.62)), -20 * back, 0, 360, 1, -1, cv2.LINE_AA)
            # lens: narrow parallelogram in front of the eye; temple arm back to the ear
            fwd = np.array([-back, 0.0]); upv = np.array([0.0, -1.0])
            lc = E + fwd * dd * 0.04 + upv * dd * 0.01
            hw, hh, sk = dd * 0.2, dd * 0.27, dd * 0.1
            quad = [lc + fwd * hw + upv * hh + fwd * sk, lc - fwd * hw * 0.6 + upv * hh * 0.95, lc - fwd * hw * 0.6 - upv * hh * 0.9, lc + fwd * hw - upv * hh + fwd * sk * 0.3]
            ear = E + np.array([back * dd * 1.75, dd * 0.22])
            info['glasses'] = dict(kind='profile', lens=np.round(quad, 1).tolist(), arm=[np.round(lc - fwd * hw * 0.6 + upv * hh * 0.6, 1).tolist(), np.round(ear, 1).tolist()])
            info['iris'] = [fd['eye_near_iris']] if 'eye_near_iris' in fd else []
            info['crown'] = crown.round(1).tolist(); info['E'] = E.tolist(); info['N'] = N.tolist(); info['back'] = float(back)
        info['mouth'] = pf.get('mouth')
    # dark regions of the upper figure are hair (the roto hair mask misses the front of the head)
    eye_y = (info['E'][1] if 'E' in info else (np.mean([p[1] for p in info.get('iris', [[0, 540]])]) if info.get('iris') else 540))
    fv = L[fig]; dark = fig & (L < (np.percentile(fv, 30) if fv.size else 0)) & (np.arange(H)[:, None] < eye_y + iod * 0.9) & (face == 0)
    dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, np.ones((11, 11), np.uint8))
    hair = hair | dark
    if 'E' in info:   # profile: the footage face mask runs over the head top; dark pixels above the brow are hair
        top = fig & (L < np.percentile(L[face > 0], 35)) & (np.arange(H)[:, None] < info['E'][1] - iod * 0.25)
        top = cv2.morphologyEx(top.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        E0 = np.array(info['E']); cv2.circle(top, (int(E0[0]), int(E0[1])), int(iod / 1.6 * 0.9), 0, -1)
        hair = hair | top; face = face & (1 - top)
    hair_designed = hair.copy()
    figure = (fig.astype(np.uint8) | face | hair_designed) > 0
    # ---- body tones: 3 levels from smoothed luminance, inside the figure, outside face/hair
    body = figure & (face == 0) & (hair_designed == 0)
    if body.sum() > 1000:
        v = L[body]; t1, t2 = np.percentile(v, 28), np.percentile(v, 62)
        lev = np.zeros((H, W), np.uint8); lev[body] = 1 + (L[body] > t1) + (L[body] > t2)   # 1 ink, 2 mid, 3 bone
    else: lev = np.zeros((H, W), np.uint8)
    smooth_fill(figure, (*BONE, 255), out, min_area=2000, step=5, it=3)
    k = np.ones((9, 9), np.uint8)
    for val, col in ((2, MID), (1, INK)):
        m = cv2.morphologyEx(((lev > 0) & (lev <= val)).astype(np.uint8), cv2.MORPH_OPEN, k)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k) & body
        smooth_fill(m, (*col, 255), out, min_area=2500, step=6, it=3, holes=False)
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
        for side in (-1, 1):
            for k_ in range(3):
                off = 0.22 + 0.24 * k_ + 0.06 * (k_ % 2)
                pts = [part + perp * side * iod_ * 0.05 * k_, part + perp * side * iod_ * (0.55 + off * 0.4) + up * iod_ * (0.05 - 0.02 * k_),
                       part + perp * side * iod_ * (0.95 + off * 0.5) - up * iod_ * 0.6, part + perp * side * iod_ * (1.0 + off * 0.55) - up * iod_ * 2.2,
                       part + perp * side * iod_ * (0.95 + off * 0.6) - up * iod_ * 4.0]
                cv2.polylines(strands, [np.round(chaikin(np.array(pts), 3)[:-6] * 4).astype(np.int32)], False, 1, 2, cv2.LINE_AA, shift=2)
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
    return info

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
    if '--frames' in a: k = a.index('--frames'); fr = tuple(map(int, a[k + 1].split(':'))); a = a[:k] + a[k + 2:]
    for J in a: run(J, fr)
