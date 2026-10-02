"""Mouth-openness track for anime faces in a clip.

Face: nagadomi's lbpcascade_animeface, smoothed over time. Mouth ROI: lower part of the face box.
Openness: area of mouth-interior pixels (dark / red-pink, low-luminance, saturated) inside the ROI.
"""
import sys, json
import numpy as np
import cv2

CASCADE = "/tmp/work/lbpcascade_animeface.xml"


def skin_ratio(frame, b):
    x, y, w, h = [int(v) for v in b]
    crop = frame[y + h // 3:y + h, x + w // 5:x + w - w // 5]
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).astype(np.float32)
    hh, ss, vv = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    return float((((hh < 40) | (hh > 340)) & (ss > 0.06) & (ss < 0.5) & (vv > 0.55)).mean())


def detect_faces(frames):
    cas = cv2.CascadeClassifier(CASCADE)
    raw = []
    for f in frames:
        g = cv2.equalizeHist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        det = cas.detectMultiScale(g, scaleFactor=1.06, minNeighbors=3, minSize=(40, 40))
        cands = [(skin_ratio(f, b), [float(v) for v in b]) for b in det]
        cands = [c for c in cands if c[0] > 0.12]
        raw.append(max(cands, key=lambda c: c[0] * c[1][2])[1] if cands else None)
    # reject detections far from the median track (e.g. round jacket patches)
    good = [b for b in raw if b is not None]
    if len(good) < 3:
        return None, 0.0
    if good:
        med = np.median(np.array(good), axis=0)
        boxes = []
        for b in raw:
            if b is None:
                boxes.append(None); continue
            cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
            mcx, mcy = med[0] + med[2] / 2, med[1] + med[3] / 2
            far = abs(cx - mcx) > 0.8 * med[2] or abs(cy - mcy) > 0.8 * med[3] or not (0.6 < b[2] / med[2] < 1.6)
            boxes.append(None if far else b)
    else:
        boxes = raw
    # fill gaps + smooth
    arr = np.array([b if b is not None else [np.nan] * 4 for b in boxes], dtype=float)
    for k in range(4):
        col = arr[:, k]
        ok = ~np.isnan(col)
        if ok.sum() == 0:
            return None, 0.0
        col[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), col[ok])
        ker = np.ones(5) / 5
        arr[:, k] = np.convolve(np.pad(col, 2, mode="edge"), ker, mode="valid")
    return arr, float(np.mean([b is not None for b in boxes]))


def mouth_roi(box, shape):
    x, y, w, h = box
    # cascade box spans roughly brows..chin; mouth sits ~72-100% down, central 40%
    x0 = int(x + 0.33 * w); x1 = int(x + 0.67 * w)
    y0 = int(y + 0.52 * h); y1 = int(y + 0.76 * h)
    H, W = shape[:2]
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def openness(frame, roi):
    x0, y0, x1, y1 = roi
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return 0.0, crop
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    skin = (((h < 40) | (h > 340)) & (s > 0.07) & (s < 0.42) & (v > 0.62))
    # central ellipse only, so hair / jaw edges at the ROI border do not count
    H, W = crop.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    ell = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2 < 1
    m = ((~skin) & ell).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return float(m.mean()), crop


def track(path, stride=1, fixed_roi=None):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    if fixed_roi is not None:
        op = [openness(f, fixed_roi)[0] for f in frames]
        return {"fps": fps, "hit": 1.0, "open": op, "fixed": list(fixed_roi)}
    boxes, hit = detect_faces(frames)
    if boxes is None:
        return {"fps": fps, "hit": 0, "open": []}
    op = []
    for f, b in zip(frames, boxes):
        o, _ = openness(f, mouth_roi(b, f.shape))
        op.append(o)
    return {"fps": fps, "hit": hit, "open": op, "boxes": boxes.tolist()}


if __name__ == "__main__":
    r = track(sys.argv[1])
    print(json.dumps({"fps": r["fps"], "hit": r["hit"], "n": len(r["open"])}))
    if len(sys.argv) > 2:
        json.dump(r, open(sys.argv[2], "w"))
