#!/usr/bin/env python3
"""Likeness gate for Jade: MediaPipe Face Landmarker + multiclass selfie segmenter.

Usage:
  python3 tools/likeness/measure.py IMG [IMG ...] [--json out.json] [--debug DIR] [--gate]
  python3 tools/likeness/measure.py --video clip.mp4 --every 12 --gate        # sample video frames

As a library:
  from measure import measure, gate, REAL
  m = measure("frame.jpg")            # dict of ratios (None if no face)
  ok, devs = gate(m)                  # compare to the real-photo mean (assets/character/v2/measure.json)

Ratios (all pose-normalized: in-plane roll removed; eye ratios use 3-D landmarks de-rotated with the
face transformation matrix so yaw/pitch mostly cancel; vertical ratios are 2-D along the face axis):
  eye_w_iod     mean eye width (inner->outer canthus) / outer-canthal distance (33-263)
  eye_open      mean lid opening (3 vertical pairs) / eye width
  eye_w_face    mean eye width / face width (234-454, cheek-to-cheek)
  iris_face     mean iris diameter / face width   (lid-independent eye-size check)
  forehead      (brow line -> hairline) / (hairline -> chin)
  browchin_face (brow line -> chin) / face height (hairline -> chin)  == 1 - forehead
  mid_third     (brow line -> subnasale) / (brow line -> chin)
  face_hw       face height (hairline -> chin) / face width
Hairline: the selfie_multiclass_256x256 segmenter (classes 0 bg,1 hair,2 body,3 face-skin,4 clothes,5 other);
from the glabella we walk up the face axis in several columns (+-0.08..0.30 face width off the midline,
skipping the centre part) until face-skin ends; the median column is the hairline.
"""
import sys, os, json, math, argparse, urllib.request
import numpy as np, cv2
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "selfie_multiclass_256x256.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
}
REAL_JSON = os.path.join(HERE, "..", "..", "assets", "character", "v2", "measure.json")
KEYS = ["eye_w_iod", "eye_open", "eye_w_face", "iris_face", "forehead", "browchin_face", "mid_third", "face_hw"]
GATE_KEYS = {"eye_w_face": 0.05, "iris_face": 0.07, "eye_open": 0.10, "forehead": 0.05}  # rel. tolerance

# landmark ids
R_OUT, R_IN, L_OUT, L_IN = 33, 133, 263, 362
R_V = [(160, 144), (159, 145), (158, 153)]
L_V = [(385, 380), (386, 374), (387, 373)]
CHEEK_R, CHEEK_L, CHIN, SUBNASALE, GLABELLA = 234, 454, 152, 2, 9
BROW_R = [70, 63, 105, 66, 107]
BROW_L = [300, 293, 334, 296, 336]
# brow contours, medial -> lateral (subject-right brow = image-left in an un-mirrored photo)
BROW_R_UP, BROW_R_LO = [107, 66, 105, 63, 70], [55, 65, 52, 53, 46]
BROW_L_UP, BROW_L_LO = [336, 296, 334, 293, 300], [285, 295, 282, 283, 276]
IRIS_R, IRIS_L = [469, 470, 471, 472], [474, 475, 476, 477]

_det = {}


def _model(name):
    p = os.path.join(MODELS, name)
    if not os.path.exists(p):
        os.makedirs(MODELS, exist_ok=True)
        urllib.request.urlretrieve(URLS[name], p)
    return p


def _mp():
    if "fl" not in _det:
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        _det["mp"] = mp
        _det["fl"] = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=_model("face_landmarker.task")),
            output_face_blendshapes=True, output_facial_transformation_matrixes=True, num_faces=3))
        _det["seg"] = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=mpt.BaseOptions(model_asset_path=_model("selfie_multiclass_256x256.tflite")),
            output_category_mask=True))
    return _det


def load_rgb(path_or_arr):
    if isinstance(path_or_arr, np.ndarray):
        return np.ascontiguousarray(path_or_arr[..., :3])
    im = ImageOps.exif_transpose(Image.open(path_or_arr)).convert("RGB")
    return np.asarray(im)


def landmarks(rgb):
    """Return (pts Nx3 in pixels, matrix 4x4, blendshapes dict) of the largest face, or None."""
    d = _mp(); mp = d["mp"]
    res = d["fl"].detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.face_landmarks:
        return None
    h, w = rgb.shape[:2]
    best = max(range(len(res.face_landmarks)),
               key=lambda i: np.ptp([p.x for p in res.face_landmarks[i]]) * np.ptp([p.y for p in res.face_landmarks[i]]))
    pts = np.array([[p.x * w, p.y * h, p.z * w] for p in res.face_landmarks[best]])
    M = np.array(res.facial_transformation_matrixes[best]) if res.facial_transformation_matrixes else np.eye(4)
    bs = {c.category_name: c.score for c in res.face_blendshapes[best]} if res.face_blendshapes else {}
    return pts, M, bs


def seg_mask(rgb):
    d = _mp(); mp = d["mp"]
    r = d["seg"].segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    m = r.category_mask.numpy_view().copy()
    return m[..., 0] if m.ndim == 3 else m


def pose_angles(M):
    R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
    yaw = math.degrees(math.atan2(-R[2, 0], math.hypot(R[0, 0], R[1, 0])))
    pitch = math.degrees(math.atan2(R[2, 1], R[2, 2]))
    roll = math.degrees(math.atan2(R[1, 0], R[0, 0]))
    return yaw, pitch, roll


def face_frame(pts):
    """Origin at glabella, unit 'up' axis from chin to glabella (2-D, roll removed)."""
    up = pts[GLABELLA, :2] - pts[CHIN, :2]
    up /= np.linalg.norm(up)
    right = np.array([-up[1], up[0]])
    return up, right


def hairline(pts, mask, debug=None):
    """Return (point xy, distance above glabella along up axis) or (None, None)."""
    up, right = face_frame(pts)
    g = pts[GLABELLA, :2]
    fw = np.linalg.norm(pts[CHEEK_L, :2] - pts[CHEEK_R, :2])
    h, w = mask.shape
    hits = []
    for off in [-0.30, -0.24, -0.18, -0.12, -0.08, 0.08, 0.12, 0.18, 0.24, 0.30]:
        base = g + right * off * fw
        prev_skin, last_skin = False, None
        for t in np.arange(0, 1.2 * fw, 1.0):
            p = base + up * t
            x, y = int(round(p[0])), int(round(p[1]))
            if not (0 <= x < w and 0 <= y < h):
                break
            c = mask[y, x]
            if c == 3 or c == 2:          # face/body skin
                last_skin = t
            elif last_skin is not None and t - last_skin > 0.03 * fw:
                break
        if last_skin is not None and last_skin > 0.05 * fw:
            # reached top of image while still on skin -> unreliable
            p = base + up * (last_skin + 1)
            if 0 <= int(p[1]) < h - 0 and int(p[1]) > 1:
                hits.append(last_skin)
    if len(hits) < 3:
        return None, None
    t = float(np.median(hits))
    return g + up * t, t


def brow_metrics(Pc, side):
    """Per-brow metrics in the de-rotated 3-D frame (x right in image, y up). Units: eye-width-normalised
    by outer-canthal distance (IOD). side 'R' = MediaPipe right = image-left unless the photo is mirrored."""
    up_ids, lo_ids = (BROW_R_UP, BROW_R_LO) if side == "R" else (BROW_L_UP, BROW_L_LO)
    eo, ei = (R_OUT, R_IN) if side == "R" else (L_OUT, L_IN)
    iod = float(np.linalg.norm(Pc[R_OUT, :2] - Pc[L_OUT, :2]))
    eye_c = (Pc[eo, :2] + Pc[ei, :2]) / 2
    up = Pc[up_ids, :2]; lo = Pc[lo_ids, :2]
    mid = (up + lo) / 2
    hts = (up[:, 1] - eye_c[1]) / iod
    k = int(np.argmax(hts))
    # parabolic refinement of arch peak along the brow (0 = medial end, 1 = lateral end)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(up, axis=0), axis=1))]; L /= L[-1]
    if 0 < k < 4:
        y0, y1, y2 = hts[k - 1], hts[k], hts[k + 1]
        den = y0 - 2 * y1 + y2
        dk = 0.5 * (y0 - y2) / den if abs(den) > 1e-9 else 0
        peak_pos = float(np.interp(k + dk, range(5), L))
    else:
        peak_pos = float(L[k])
    med, lat = mid[0], mid[-1]
    sgn = -1 if side == "R" else 1             # lateral direction: -x for image-left brow
    ang = math.degrees(math.atan2(lat[1] - med[1], sgn * (lat[0] - med[0])))  # + = lateral end higher
    arch = float(hts.max() - (hts[0] + hts[-1]) / 2)
    return dict(height=round(float(hts.mean()), 4), peak_height=round(float(hts.max()), 4),
                peak_pos=round(peak_pos, 3), angle=round(ang, 2), arch=round(arch, 4),
                thick=round(float(np.mean(np.linalg.norm(up - lo, axis=1)) / iod), 4),
                length=round(float(np.linalg.norm(lat - med) / iod), 4))


def measure(src, debug_path=None):
    rgb = load_rgb(src)
    lm = landmarks(rgb)
    if lm is None:
        return None
    pts, M, bs = lm
    yaw, pitch, roll = pose_angles(M)
    # 3-D de-rotation for eye ratios
    R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
    P = pts.copy(); P[:, 1] *= -1; P[:, 2] *= -1          # to right-handed y-up
    Pc = (P - P.mean(0)) @ R                               # undo head rotation
    d3 = lambda a, b: float(np.linalg.norm(Pc[a] - Pc[b]))
    ew = (d3(R_OUT, R_IN) + d3(L_OUT, L_IN)) / 2
    iod = d3(R_OUT, L_OUT)
    op = (np.mean([d3(a, b) for a, b in R_V]) / d3(R_OUT, R_IN) + np.mean([d3(a, b) for a, b in L_V]) / d3(L_OUT, L_IN)) / 2
    fw3 = d3(CHEEK_R, CHEEK_L)
    iris = []
    if pts.shape[0] >= 478:
        iris = [(d3(IRIS_R[0], IRIS_R[2]) + d3(IRIS_R[1], IRIS_R[3])) / 2, (d3(IRIS_L[0], IRIS_L[2]) + d3(IRIS_L[1], IRIS_L[3])) / 2]
    out = dict(yaw=round(yaw, 1), pitch=round(pitch, 1), roll=round(roll, 1),
               eye_w_iod=ew / iod, eye_open=op, eye_w_face=ew / fw3,
               iris_face=(np.mean(iris) / fw3) if iris else None,
               blink=round((bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2, 3),
               squint=round((bs.get("eyeSquintLeft", 0) + bs.get("eyeSquintRight", 0)) / 2, 3))
    bR, bL = brow_metrics(Pc, "R"), brow_metrics(Pc, "L")
    out["eye_roll_check"] = round(math.degrees(math.atan2(Pc[L_OUT, 1] - Pc[R_OUT, 1], Pc[L_OUT, 0] - Pc[R_OUT, 0])), 2)
    # image-left / image-right brows (raw); subject sides depend on mirroring (see notes in measure.json)
    out["brow_imgL"], out["brow_imgR"] = bR, bL
    out["brow_asym"] = {k: round(bR[k] - bL[k], 4) for k in bR}   # image-left minus image-right
    # vertical ratios along face axis (2-D)
    up, right = face_frame(pts)
    ax = lambda i: float(np.dot(pts[i, :2] - pts[GLABELLA, :2], up))
    brow = float(np.mean([ax(i) for i in BROW_R + BROW_L]))
    chin, subn = ax(CHIN), ax(SUBNASALE)
    mask = seg_mask(rgb)
    hp, ht = hairline(pts, mask)
    out["mid_third"] = (brow - subn) / (brow - chin)
    if ht is not None:
        fh = ht - chin
        out["forehead"] = (ht - brow) / fh
        out["browchin_face"] = (brow - chin) / fh
        out["face_hw"] = fh / np.linalg.norm(pts[CHEEK_L, :2] - pts[CHEEK_R, :2])
        out["hairline_xy"] = [round(float(hp[0]), 1), round(float(hp[1]), 1)]
    else:
        out.update(forehead=None, browchin_face=None, face_hw=None)
    out["face_px"] = round(float(np.linalg.norm(pts[CHEEK_L, :2] - pts[CHEEK_R, :2])), 1)
    for k in KEYS:
        if out.get(k) is not None:
            out[k] = round(float(out[k]), 4)
    if debug_path:
        dbg = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR).copy()
        col = np.array([[0, 0, 0], [0, 200, 255], [255, 0, 255], [0, 255, 0], [255, 0, 0], [0, 0, 255]], np.uint8)
        mm = cv2.resize(col[mask], (dbg.shape[1], dbg.shape[0]), interpolation=cv2.INTER_NEAREST) if mask.shape != dbg.shape[:2] else col[mask]
        dbg = cv2.addWeighted(dbg, 0.7, mm, 0.3, 0)
        for i in [R_OUT, R_IN, L_OUT, L_IN, CHEEK_R, CHEEK_L, CHIN, SUBNASALE, GLABELLA] + BROW_R + BROW_L:
            cv2.circle(dbg, tuple(int(v) for v in pts[i, :2]), max(2, int(out["face_px"] / 150)), (0, 0, 255), -1)
        for a, b in R_V + L_V:
            cv2.line(dbg, tuple(int(v) for v in pts[a, :2]), tuple(int(v) for v in pts[b, :2]), (255, 255, 0), 1)
        if ht is not None:
            cv2.circle(dbg, tuple(int(v) for v in hp), max(3, int(out["face_px"] / 80)), (0, 255, 255), -1)
        cv2.imwrite(debug_path, dbg)
    return out


def real_ref():
    try:
        return json.load(open(REAL_JSON))["real"]["mean"]
    except Exception:
        return None


def gate(m, ref=None, tol=None):
    """Return (ok, {key: relative deviation}). Smaller eyes or forehead beyond tolerance fail; larger
    eyes only fail if > 2x tolerance."""
    ref = ref or real_ref(); tol = tol or GATE_KEYS
    if m is None or ref is None:
        return False, {}
    devs, ok = {}, True
    for k, t in tol.items():
        if m.get(k) is None or ref.get(k) is None:
            continue
        d = m[k] / ref[k] - 1
        devs[k] = round(d, 4)
        if d < -t or d > 2 * t:
            ok = False
    return ok, devs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imgs", nargs="*")
    ap.add_argument("--json"); ap.add_argument("--debug"); ap.add_argument("--gate", action="store_true")
    ap.add_argument("--video"); ap.add_argument("--every", type=int, default=12)
    a = ap.parse_args()
    items = [(p, p) for p in a.imgs]
    if a.video:
        cap = cv2.VideoCapture(a.video); i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if i % a.every == 0:
                items.append((f"{a.video}#{i}", cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
            i += 1
    res = {}
    for name, src in items:
        dbg = os.path.join(a.debug, os.path.basename(str(name)).replace("#", "_") + ".dbg.jpg") if a.debug else None
        if dbg: os.makedirs(a.debug, exist_ok=True)
        m = measure(src, dbg)
        if m and a.gate:
            m["gate_ok"], m["gate_dev"] = gate(m)
        res[name] = m
        print(name, json.dumps(m))
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
