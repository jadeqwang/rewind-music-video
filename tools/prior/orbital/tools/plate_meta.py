"""Per-frame plate measurements the renderer uses to lock procedural layers onto the footage.

For every extracted plate frame (video/plates/<id>/f*.jpg) record:
  sun:  [u, v, strength]  centroid of the brightest near-white blob (u, v in 0..1), strength 0..1
  lum:  mean luminance 0..1
  hot:  fraction of near-white pixels (flash / flare amount)
  face: [u0, v0, u1, v1, jawOpen, eyeLx, eyeLy, eyeRx, eyeRy, mouthX, mouthY] for the largest face, or null
Writes video/plates/<id>/meta.json. Run after tools/extract_plates.py.
Face model: MediaPipe face landmarker (/tmp/work/models/face_landmarker.task).
"""
import sys, json, pathlib, os
import numpy as np, cv2

ROOT = pathlib.Path(__file__).resolve().parent.parent
DST = ROOT / "video" / "plates"
MODEL = os.environ.get("FACE_MODEL", "/tmp/work/models/face_landmarker.task")
_fl = None


def landmarker():
    global _fl
    if _fl is None and os.path.exists(MODEL):
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        opts = vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=MODEL), output_face_blendshapes=True,
                                            running_mode=vision.RunningMode.IMAGE, num_faces=3, min_face_detection_confidence=0.3)
        _fl = (mp, vision.FaceLandmarker.create_from_options(opts))
    return _fl


# ordered landmark polylines (MediaPipe face mesh indices) for drawing faces as line work
FEATURES = {
    "oval": [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10],
    "eyeR_up": [33, 246, 161, 160, 159, 158, 157, 173, 133], "eyeR_lo": [33, 7, 163, 144, 145, 153, 154, 155, 133],
    "eyeL_up": [362, 398, 384, 385, 386, 387, 388, 466, 263], "eyeL_lo": [362, 382, 381, 380, 374, 373, 390, 249, 263],
    "browR": [46, 53, 52, 65, 55], "browRu": [70, 63, 105, 66, 107], "browL": [276, 283, 282, 295, 285], "browLu": [300, 293, 334, 296, 336],
    "nose": [168, 6, 197, 195, 5, 4], "noseB": [64, 98, 97, 2, 326, 327, 294],
    "lipO_up": [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291], "lipO_lo": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291],
    "lipI_up": [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308], "lipI_lo": [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308],
}
IRIS = {"irisR": [468, 469, 470, 471, 472], "irisL": [473, 474, 475, 476, 477]}


def _detect(rgb):
    mp, det = landmarker()
    return det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))


class _R:  # minimal stand-in for a detection result with remapped landmarks
    def __init__(self, lms, bss):
        self.face_landmarks, self.face_blendshapes = lms, bss


class _P:
    def __init__(self, x, y):
        self.x, self.y = x, y


def _detect_robust(rgb):
    """Full frame first; then upscaled crops and small rotations (upturned or small faces)."""
    r = _detect(rgb)
    if r.face_landmarks:
        return r
    H, W = rgb.shape[:2]
    for (x0, y0, x1, y1) in [(.15, 0, .85, .75), (0, 0, .6, .7), (.4, 0, 1, .7), (.25, .1, .75, .9)]:
        X0, Y0, X1, Y1 = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
        crop = cv2.resize(rgb[Y0:Y1, X0:X1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for ang in (0, 12, -12):
            if ang:
                M = cv2.getRotationMatrix2D((crop.shape[1] / 2, crop.shape[0] / 2), ang, 1.0)
                img = cv2.warpAffine(crop, M, (crop.shape[1], crop.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                Mi = cv2.invertAffineTransform(M)
            else:
                img, Mi = crop, None
            rr = _detect(img)
            if rr.face_landmarks:
                out = []
                for lms in rr.face_landmarks:
                    pts = []
                    for p in lms:
                        px, py = p.x * img.shape[1], p.y * img.shape[0]
                        if Mi is not None:
                            px, py = Mi[0, 0] * px + Mi[0, 1] * py + Mi[0, 2], Mi[1, 0] * px + Mi[1, 1] * py + Mi[1, 2]
                        pts.append(_P((X0 + px / 2) / W, (Y0 + py / 2) / H))
                    out.append(pts)
                return _R(out, rr.face_blendshapes)
    return r


def face_of(rgb):
    fl = landmarker()
    if not fl:
        return None
    r = _detect_robust(rgb)
    if not r.face_landmarks:
        return None
    best, area = None, 0
    for i, lms in enumerate(r.face_landmarks):
        lm = np.array([[p.x, p.y] for p in lms])
        a = np.prod(lm.max(0) - lm.min(0))
        if a > area:
            area, best = a, (lm, {b.category_name: b.score for b in r.face_blendshapes[i]})
    lm, bs = best
    (u0, v0), (u1, v1) = lm.min(0), lm.max(0)
    eyeL, eyeR, mouth = lm[[33, 133]].mean(0), lm[[362, 263]].mean(0), lm[[13, 14]].mean(0)
    base = [round(float(x), 4) for x in (u0, v0, u1, v1, bs.get("jawOpen", 0), *eyeL, *eyeR, *mouth)]
    lines = {k: [round(float(c), 4) for i in idx for c in lm[i]] for k, idx in FEATURES.items()}
    if len(lm) >= 478:
        for k, idx in IRIS.items():
            c = lm[idx[0]]; r = float(np.mean(np.linalg.norm(lm[idx[1:]] - c, axis=1)))
            lines[k] = [round(float(c[0]), 4), round(float(c[1]), 4), round(r, 4)]
    return base + [lines]


def measure(path):
    bgr = cv2.imread(str(path))
    im = cv2.resize(bgr, (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    L = im[..., 2] * .2126 + im[..., 1] * .7152 + im[..., 0] * .0722
    hot = (L > .92).astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), 3)
    y, x = np.unravel_index(np.argmax(Lb), Lb.shape)
    peak = float(Lb[y, x])
    if hot.sum() > 3:
        ys, xs = np.nonzero(cv2.GaussianBlur(hot, (0, 0), 2) > .5)
        if len(xs):
            d = (xs - x) ** 2 + (ys - y) ** 2
            sel = d < (d.min() + 400)
            x, y = xs[sel].mean(), ys[sel].mean()
    return {"sun": [round(float(x) / 320, 4), round(float(y) / 180, 4), round(min(1.0, max(0.0, (peak - .6) / .4)), 3)],
            "lum": round(float(L.mean()), 4), "hot": round(float(hot.mean()), 5),
            "face": face_of(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))}


def stats(pid):
    """Per-plate exposure gain: the 95th-percentile luminance across the take maps to 0.85 (never darkens)."""
    d = DST / pid
    frames = sorted(d.glob("f*.jpg"))
    pick = frames[::max(1, len(frames) // 12)]
    p95 = []
    for f in pick:
        im = cv2.resize(cv2.imread(str(f)), (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        L = im[..., 2] * .2126 + im[..., 1] * .7152 + im[..., 0] * .0722
        p95.append(np.percentile(L, 95))
    gain = float(np.clip(.85 / max(np.median(p95), 1e-3), 1.0, 2.2))
    (d / "stats.json").write_text(json.dumps({"p95": round(float(np.median(p95)), 3), "gain": round(gain, 3)}))
    return gain


def run(pid, force=False):
    d = DST / pid
    frames = sorted(d.glob("f*.jpg"))
    stats(pid)
    out = d / "meta.json"
    if out.exists() and not force:
        try:
            old = json.loads(out.read_text())
            if len(old) == len(frames) and "face" in old[0] and (not any(m["face"] for m in old) or any(m["face"] and len(m["face"]) > 11 for m in old)):
                return
        except Exception:
            pass
    meta = [measure(f) for f in frames]
    out.write_text(json.dumps(meta, separators=(",", ":")))
    s = [m["sun"][2] for m in meta]
    nf = sum(1 for m in meta if m["face"])
    print(f"{pid}: {len(meta)} frames, faces in {nf}, sun max {max(s):.2f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    force = "--force" in a
    ids = [x for x in a if not x.startswith("--")] or [p.name for p in sorted(DST.iterdir()) if p.is_dir()]
    for pid in ids:
        run(pid, force)
