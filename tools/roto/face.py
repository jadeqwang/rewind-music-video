# Face layers for Jade shots (J*): footage landmarks are ANCHORS ONLY; eyes / brows / crease come from her canonical
# real-photo template (tools/roto/template.py). See docs/LIKENESS_RULES.md.
#
# front mode   MediaPipe Face Landmarker on the 1080p frame -> facial transformation matrix (yaw/pitch/roll) +
#              canthi midpoint (anchor) + face width (scale; the footage canthi drift inward as Seedance shrinks the eyes,
#              so scale = real iod/fw ratio x footage face width, median-smoothed). The 3-D template is rotated by the
#              footage pose and projected (orthographic), so 3/4 views foreshorten the far eye naturally.
#              Openness: the template's real opening, always; only a real blink (blendshape eyeBlink > 0.6) closes it.
#              Gaze: footage iris offset (de-rotated, in eye widths, clamped) moves the template iris.
# profile mode MediaPipe cannot see profiles. tools/roto/anchors/<SHOT>.json gives the iris centre E and nose tip N on
#              frame 0 (source px); the head is tracked with KLT features + RANSAC similarity, and the hand-annotated
#              profile template (jade_profile.json, from refs/jade/PXL_20260929_003030232.jpg) is mapped E,N -> E,N.
# Lines inside the face mask are suppressed by roto.py; the jaw / nose-tip mark / hair come from the footage.
import os, json, math
import numpy as np, cv2
import template as TP

OW, OH = 1920, 1080
S = 4   # supersample for drawing
HERE = os.path.dirname(os.path.abspath(__file__))

FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150,
             136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
JAW = [132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361]
LIPS_OUT = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
EYES = dict(R=(33, 133, [468], 'eyeBlinkLeft'), L=(263, 362, [473], 'eyeBlinkRight'))
# MediaPipe blendshape names are from the subject's point of view mirrored to the image: eyeBlinkLeft = image-left eye.


def chaikin(pts, it=2, closed=False):
    P = np.asarray(pts, np.float32)
    for _ in range(it):
        Q = np.roll(P, -1, 0) if closed else P[1:]
        P0 = P if closed else P[:-1]
        a = 0.75 * P0 + 0.25 * Q; b = 0.25 * P0 + 0.75 * Q
        mid = np.stack([a, b], 1).reshape(-1, 2)
        P = mid if closed else np.concatenate([P[:1], mid, P[-1:]])
    return P


class Canvas:
    def __init__(self):
        self.c = np.zeros((OH * S, OW * S), np.uint8)

    def line(self, pts, w, closed=False):
        Q = np.round(np.asarray(pts, np.float32) * S * 4).astype(np.int32)
        cv2.polylines(self.c, [Q], closed, 255, max(1, int(round(w * S))), cv2.LINE_AA, shift=2)

    def fill(self, pts, val=255):
        cv2.fillPoly(self.c, [np.round(np.asarray(pts, np.float32) * S * 4).astype(np.int32)], val, cv2.LINE_AA, shift=2)

    def out(self):
        return cv2.resize(self.c, (OW, OH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def brow_shape(up, lo):
    """Filled brow from its own upper/lower contour, tapered toward both ends (medial 55 %, lateral 25 % thickness)."""
    up, lo = np.asarray(up, np.float32), np.asarray(lo, np.float32)
    n = len(up); t = np.linspace(0, 1, n)
    k = np.clip(np.minimum(0.55 + t / 0.25 * 0.45, 1.0) * np.minimum(1.0, 0.25 + (1 - t) / 0.35 * 0.75), 0.2, 1)[:, None]
    mid = (up + lo) / 2
    return np.concatenate([mid + (up - mid) * k, (mid + (lo - mid) * k)[::-1]])


def draw_eye(can, U, L, iris_c, iris_r, lw, closure=1.0):
    """U, L: upper / lower lid (outer -> inner canthus) in 1080p px. closure 1 = open (template), 0 = shut.
    Iris is clipped by the lid polygon. A fine double-eyelid crease follows the upper lid."""
    U = np.asarray(U, np.float32); L = np.asarray(L, np.float32)
    Uc = L + (U - L) * closure
    Uc = chaikin(Uc); Lc = chaikin(L)
    eh = float(np.linalg.norm(U[len(U) // 2] - L[len(L) // 2]))
    if closure > 0.25:
        m = np.zeros((OH * S, OW * S), np.uint8)
        poly = np.concatenate([Uc, Lc[::-1]])
        cv2.fillPoly(m, [np.round(poly * S * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
        ir = np.zeros_like(m)
        cv2.circle(ir, (int(iris_c[0] * S), int(iris_c[1] * S)), int(iris_r * S), 255, -1, cv2.LINE_AA)
        can.c = np.maximum(can.c, (ir.astype(np.uint16) * m // 255).astype(np.uint8))
    can.line(Uc, lw * 1.7); can.line(Lc, lw * 0.8)
    # crease: upper lid lifted by ~38 % of the (template) opening along the lid normal, inner 30 % -> outer end
    nrm = (U[len(U) // 2] - L[len(L) // 2]); nrm = nrm / (np.linalg.norm(nrm) + 1e-6)
    k0 = int(len(Uc) * 0.3)
    side_in = 0 if np.linalg.norm(Uc[0] - Uc[-1]) == 0 else None
    cr = Uc[:len(Uc) - k0] + nrm * max(2.0, eh * 0.38 * max(closure, 0.6))
    can.line(cr, lw * 0.55)
    return dict(upper=Uc.round(1).tolist(), lower=Lc.round(1).tolist(), crease=cr.round(1).tolist(),
                iris=[round(float(iris_c[0]), 1), round(float(iris_c[1]), 1), round(float(iris_r), 1)], closure=round(float(closure), 3))


# ---------------------------------------------------------------------------------------------------------------
class FaceTracker:
    """Per-shot state (sequential): scale smoothing, last pose, profile KLT similarity."""

    def __init__(self, shot, src_scale):
        self.scale_hist = []; self.last = None; self.miss = 0
        self.k = src_scale                      # source px -> 1080p px
        ap = os.path.join(HERE, 'anchors', f'{shot}.json')
        self.anch = json.load(open(ap)) if os.path.exists(ap) else None
        self.A = None; self.prev_g = None; self.pts = None

    # -------- profile tracking (source resolution) --------
    def track(self, src_bgr, i):
        g = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY)
        a = self.anch
        E0, N0 = np.array(a['E'], np.float32), np.array(a['N'], np.float32)
        if self.A is None:
            self.A = np.array([[1, 0, 0], [0, 1, 0]], np.float32)
        else:
            if self.pts is not None and len(self.pts) >= 6:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(self.prev_g, g, self.pts, None, winSize=(21, 21), maxLevel=3)
                back, st2, _ = cv2.calcOpticalFlowPyrLK(g, self.prev_g, nxt, None, winSize=(21, 21), maxLevel=3)
                ok = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(back - self.pts, axis=2)[:, 0] < 1.0)
                if ok.sum() >= 6:
                    M, inl = cv2.estimateAffinePartial2D(self.pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5)
                    if M is not None:
                        A3 = np.vstack([self.A, [0, 0, 1]]); M3 = np.vstack([M, [0, 0, 1]])
                        self.A = (M3 @ A3)[:2].astype(np.float32)
        # re-seed features on the face (around the transformed anchors) every drawing
        E = self.A @ np.r_[E0, 1]; N = self.A @ np.r_[N0, 1]
        r = 2.2 * float(np.linalg.norm(E - N))
        m = np.zeros_like(g); cv2.circle(m, (int((E[0] + N[0]) / 2), int((E[1] + N[1]) / 2)), int(r), 255, -1)
        self.pts = cv2.goodFeaturesToTrack(g, 80, 0.01, 4, mask=m)
        self.prev_g = g
        return E, N

    def smooth_scale(self, s):
        self.scale_hist = (self.scale_hist + [s])[-9:]
        return float(np.median(self.scale_hist))


def landmarks(bgr_full):
    from roto import mp_task, mp_image
    res = mp_task('face').detect(mp_image(bgr_full))
    if not res.face_landmarks:
        return None
    lm = res.face_landmarks[0]
    pts = np.array([[p.x * OW, p.y * OH, p.z * OW] for p in lm], np.float32)
    M = np.array(res.facial_transformation_matrixes[0]) if res.facial_transformation_matrixes else np.eye(4)
    bs = {c.category_name: c.score for c in res.face_blendshapes[0]} if res.face_blendshapes else {}
    return pts, M, bs


def seg_maps(bgr_full):
    from roto import mp_task, mp_image
    sres = mp_task('seg').segment(mp_image(bgr_full))
    conf = [np.squeeze(c.numpy_view()) for c in sres.confidence_masks]
    gg = cv2.cvtColor(bgr_full, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    def ref(c):
        c = cv2.resize(c, (OW, OH)).astype(np.float32)
        return np.clip((cv2.ximgproc.guidedFilter(gg, c, 8, 2e-3) - 0.5) * 2.2 + 0.5, 0, 1)
    hair = ref(conf[1]) if len(conf) > 1 else np.zeros((OH, OW), np.float32)
    skin = ref(conf[3]) if len(conf) > 3 else np.zeros((OH, OW), np.float32)
    return hair, skin


def front(can, pts, M, bs, trk, poly):
    T = TP.load('front')
    c, R, iod3 = TP.canon(pts, M)                           # footage, canonical
    fw = float(np.linalg.norm(c[234] - c[454])) * iod3      # face width in footage px (3-D, de-rotated)
    s = trk.smooth_scale(T['iod_over_fw'] * fw)             # template IOD in 1080p px
    o2 = (pts[33, :2] + pts[263, :2]) / 2                   # anchor: canthi midpoint (2-D)
    Rr = R

    def proj(P):
        P = np.asarray(P, np.float32) * s
        W = P @ Rr.T
        return np.stack([o2[0] + W[:, 0], o2[1] - W[:, 1]], 1)
    lw = max(1.3, s / 70)
    import measure as MS
    yaw = float(MS.pose_angles(M)[0])
    eyes = {}
    for side in 'RL':
        oc, ic, iris_ids, bkey = EYES[side]
        # skip the far eye when it would be hidden behind the nose
        if (side == 'R' and yaw < -42) or (side == 'L' and yaw > 42):
            continue
        U, L = np.array(T[f'eye_{side}_up']), np.array(T[f'eye_{side}_lo'])
        # iris: centred in the template opening + footage gaze offset (de-rotated, in eye widths, clamped)
        ew_t = np.linalg.norm(U[0, :2] - U[-1, :2])
        ctr_t = np.r_[(np.r_[U, L][:, :2]).mean(0), U[:, 2].mean()]
        fe = (c[oc] + c[ic]) / 2; few = np.linalg.norm(c[oc, :2] - c[ic, :2]) + 1e-6
        g = (c[iris_ids[0], :2] - fe[:2]) / few
        g = np.clip(g, [-0.22, -0.12], [0.22, 0.12])
        ic3 = ctr_t.copy(); ic3[:2] += g * ew_t
        closure = 1.0
        b = (bs.get('eyeBlinkLeft', 0.0) + bs.get('eyeBlinkRight', 0.0)) / 2   # blinks are bilateral; side naming is ambiguous
        if b > 0.6:
            closure = float(np.clip(1 - (b - 0.6) / 0.25, 0.0, 1.0))
        Up, Lp = proj(U), proj(L)
        icp = proj(ic3[None])[0]
        ir = T[f'iris_{side}'][3] * s * 0.95
        eyes[side] = draw_eye(can, Up, Lp, icp, ir, lw, closure)
        br = brow_shape(proj(T[f'brow_{side}_up']), proj(T[f'brow_{side}_lo']))
        can.fill(br)
        poly[f'brow_{side}'] = br.round(1).tolist()
    for side, e in eyes.items():
        for k, v in e.items():
            poly[f'eye_{side}_{k}'] = v
    poly['template_scale_px'] = round(s, 2); poly['yaw'] = round(yaw, 1)
    return lw, s


def profile(can, E, N, trk, poly):
    T = TP.load('profile')
    pe, pn = np.array(T['E'], np.float32), np.array(T['N'], np.float32)
    v0, v1 = pn - pe, N - E
    sc = np.linalg.norm(v1) / np.linalg.norm(v0)
    ang = math.atan2(v1[1], v1[0]) - math.atan2(v0[1], v0[0])
    Rm = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]], np.float32) * sc
    f = lambda P: ((np.asarray(P, np.float32) - pe) @ Rm.T + E) * trk.k
    lw = max(1.3, sc * trk.k * T['lw_photo'])
    U, L = f(T['eye_up']), f(T['eye_lo'])
    ic = f([T['iris'][:2]])[0]; r = T['iris'][2] * sc * trk.k
    # profile iris is an ellipse (rx = ratio * ry); draw it clipped by the lids
    m = np.zeros((OH * S, OW * S), np.uint8)
    poly_e = np.concatenate([chaikin(U), chaikin(L)[::-1]])
    cv2.fillPoly(m, [np.round(poly_e * S * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
    ir = np.zeros_like(m)
    cv2.ellipse(ir, (int(ic[0] * S), int(ic[1] * S)), (int(r * T['iris_ratio'] * S), int(r * S)), math.degrees(ang), 0, 360, 255, -1, cv2.LINE_AA)
    can.c = np.maximum(can.c, (ir.astype(np.uint16) * m // 255).astype(np.uint8))
    can.line(chaikin(U), lw * 1.7); can.line(chaikin(L), lw * 0.8)
    cr = chaikin(f(T['crease'])); can.line(cr, lw * 0.55)
    br = brow_shape(chaikin(f(T['brow_up'])), chaikin(f(T['brow_lo'])))
    can.fill(br)
    poly.update(eye_near_upper=chaikin(U).round(1).tolist(), eye_near_lower=chaikin(L).round(1).tolist(),
                eye_near_crease=cr.round(1).tolist(), eye_near_iris=[round(float(ic[0]), 1), round(float(ic[1]), 1), round(r, 1)],
                brow_near=br.round(1).tolist(), E=(E * trk.k).round(1).tolist(), N=(N * trk.k).round(1).tolist(),
                template_scale=round(float(sc * trk.k), 4))
    return lw, sc


def face_layers(bgr_full, src_bgr, trk, i):
    hair, skin = seg_maps(bgr_full)
    can = Canvas(); facem = np.zeros((OH, OW), np.uint8)
    poly = {}; mouth = None; tilt = None; mouth_open = None
    lm = landmarks(bgr_full)
    mode = None
    if lm is not None:
        pts, M, bs = lm
        mode = 'front'
        lw, s = front(can, pts, M, bs, trk, poly)
        P = pts[:, :2]
        # footage anchors only: jaw (lower), nose-tip mark, face oval mask, mouth track
        can.line(chaikin(P[JAW], 2), lw * 1.2)
        iod = float(np.linalg.norm(P[33] - P[263]))
        c2 = P[2]
        nose = chaikin([c2 * 0.62 + P[98] * 0.38 - (0, iod * 0.012), c2 + (0, iod * 0.012), c2 * 0.62 + P[327] * 0.38 - (0, iod * 0.012)])
        can.line(nose, lw * 1.1)
        oval = chaikin(P[FACE_OVAL], 2, True)
        cv2.fillPoly(facem, [np.round(oval * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
        poly.update(jaw=chaikin(P[JAW], 2).round(1).tolist(), nose=nose.round(1).tolist(),
                    lips=chaikin(P[LIPS_OUT], 1, True).round(1).tolist())
        mouth = [round(float((P[61][0] + P[291][0]) / 2), 1), round(float((P[13][1] + P[14][1]) / 2), 1),
                 round(float(np.linalg.norm(P[61] - P[291])), 1)]
        mouth_open = round(float(np.linalg.norm(P[13] - P[14]) / max(1.0, iod)), 4)
        tilt = round(float(math.atan2(P[263][1] - P[33][1], P[263][0] - P[33][0])), 4)
        trk.last = (pts, M, bs); trk.miss = 0
        if trk.anch is not None:
            trk.track(src_bgr, i)          # keep the profile tracker alive through frontal stretches
    elif trk.anch is not None:
        mode = 'profile'
        E, N = trk.track(src_bgr, i)
        profile(can, E, N, trk, poly)
        a = trk.anch
        if 'mouth' in a:                  # mouth corner tracked with the head
            mc = trk.A @ np.r_[np.array(a['mouth'], np.float32), 1] * trk.k
            mouth = [round(float(mc[0]), 1), round(float(mc[1]), 1), round(float(np.linalg.norm(E - N) * trk.k * 0.9), 1)]
        tilt = round(float(math.atan2(trk.A[1, 0], trk.A[0, 0])), 4)
        facem = (skin > 0.5).astype(np.uint8) * 255
    elif trk.last is not None and trk.miss < 3:     # brief detection dropout: hold the last pose
        trk.miss += 1
        pts, M, bs = trk.last
        mode = 'front_hold'
        front(can, pts, M, {}, trk, poly)
        P = pts[:, :2]
        oval = chaikin(P[FACE_OVAL], 2, True)
        cv2.fillPoly(facem, [np.round(oval * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
    face = cv2.dilate(facem, np.ones((5, 5), np.uint8)).astype(np.float32) / 255
    face = np.maximum(face, skin * (face > 0)) if mode == 'front' else face
    face = face * (1 - np.clip((hair - 0.5) * 2, 0, 1))
    poly['mode'] = mode
    return dict(face=face, features=can.out(), hair=hair, poly=poly if mode else None, mouth=mouth, tilt=tilt,
                mouth_open=mouth_open, mode=mode)
