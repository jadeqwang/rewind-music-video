#!/usr/bin/env python3
"""Eye-size gate for anime frames / clips vs the canon heads (CANON_HEAD_front / _34).
Finds the face (MediaPipe), crops it with margin, upscales to ~700 px, runs tools/likeness/measure.measure().
  framemeasure.py IMG.jpg [IMG2 ...]          -> per image: yaw, eye_w_face, iris_face, eye_open and % vs canon
  framemeasure.py --clip CLIP.mp4 [n=8]        -> same on n sampled frames
Canon ratio picked by |yaw| (<15 front, else 3/4)."""
import sys, json, numpy as np, cv2
sys.path.insert(0, "/home/user/rewind-music-video/tools/likeness")
import measure as MS
from PIL import Image
A = "/home/user/rewind-music-video/assets/character/anime"
K = ["eye_w_face", "iris_face", "eye_open"]

def lift(rgb):
    x = (rgb.astype(np.float32) / 255) ** 0.6 * 255; return x.clip(0, 255).astype(np.uint8)

def find_face(rgb):
    h, w = rgb.shape[:2]
    for g in (False, True):
        src = lift(rgb) if g else rgb
        fs = MS.all_faces(np.ascontiguousarray(src))
        if fs:
            return max(fs, key=lambda q: q["box"][2] - q["box"][0])["box"]
        for frac in (0.6, 0.4, 0.25):            # overlapping windows, upscaled
            ws = int(min(h, w) * frac); st = ws // 2; best = None
            for y in range(0, max(1, h - ws + 1), st):
                for x in range(0, max(1, w - ws + 1), st):
                    t = cv2.resize(src[y:y + ws, x:x + ws], (768, 768), interpolation=cv2.INTER_CUBIC)
                    fs = MS.all_faces(np.ascontiguousarray(t))
                    for q in fs:
                        b = [x + q["box"][0] * ws / 768, y + q["box"][1] * ws / 768, x + q["box"][2] * ws / 768, y + q["box"][3] * ws / 768]
                        if best is None or (b[2] - b[0]) > (best[2] - best[0]): best = b
            if best: return best
    return None

def face_measure(rgb):
    h, w = rgb.shape[:2]; box = find_face(rgb)
    if box is None:
        return None
    f = {"box": box}
    x0, y0, x1, y1 = f["box"]; s = max(x1 - x0, y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    X0, Y0 = int(max(0, cx - s)), int(max(0, cy - s)); X1, Y1 = int(min(w, cx + s)), int(min(h, cy + s))
    crop = rgb[Y0:Y1, X0:X1]
    if crop.mean() < 70: crop = lift(crop)
    sc = 700 / max(crop.shape[:2])
    crop = np.ascontiguousarray(cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC))
    m = MS.measure(crop)
    if m: m["face_px"] = round(s, 1)
    return m

CANON = {}
def canon():
    if not CANON:
        for k in ("front", "34"):
            CANON[k] = face_measure(np.array(Image.open(f"{A}/CANON_HEAD_{k}.jpg").convert("RGB")))
    return CANON

def report(name, m):
    if not m:
        print(f"{name}: no face"); return None
    c = canon()["front" if abs(m["yaw"]) < 15 else "34"]
    d = {k: round(100 * (m[k] / c[k] - 1), 1) for k in K if m.get(k) and c.get(k)}
    print(f"{name}: yaw {m['yaw']:.0f} face {m['face_px']}px " + " ".join(f"{k} {m[k]:.3f} ({d.get(k):+}%)" for k in K if m.get(k)))
    return d

if __name__ == "__main__" and sys.argv[1] != "--fix":
    a = sys.argv[1:]
    c = canon(); print("canon:", {k: {q: round(v[q], 3) for q in K + ["yaw"]} for k, v in c.items()})
    if a[0] == "--clip":
        cap = cv2.VideoCapture(a[1]); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); N = int(a[2]) if len(a) > 2 else 8
        res = []
        for i in np.linspace(0, n - 1, N).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, fr = cap.read()
            if ok: res.append(report(f"f{i}", face_measure(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))))
        ds = [r for r in res if r]
        if ds: print("MEAN", {k: round(float(np.mean([r[k] for r in ds if k in r])), 1) for k in K}, f"faces {len(ds)}/{len(res)}")
    else:
        for p in a: report(p.split("/")[-1], face_measure(np.array(Image.open(p).convert("RGB"))))

def eyefix(path, out, tol=0.05):
    """Enlarge eyes (size only, never shrink, lid opening left to the expression) back to the canon ratios inside the face crop."""
    import warp as W
    rgb = np.array(Image.open(path).convert("RGB")); h, w = rgb.shape[:2]; box = find_face(rgb)
    x0, y0, x1, y1 = box; s = max(x1 - x0, y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    X0, Y0 = int(max(0, cx - s)), int(max(0, cy - s)); X1, Y1 = int(min(w, cx + s)), int(min(h, cy + s))
    crop = rgb[Y0:Y1, X0:X1]; sc = 700 / max(crop.shape[:2])
    big = np.ascontiguousarray(cv2.resize(crop, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC))
    det = lift(big) if big.mean() < 70 else big
    m = MS.measure(det); c = canon()["front" if abs(m["yaw"]) < 15 else "34"]
    ref = dict(eye_w_face=c["eye_w_face"] * (1 - 0.01), iris_face=c["iris_face"] * (1 - 0.01), eye_open=1e-6)
    lm = MS.landmarks(det); pts = lm[0]
    want = [ref[k] / m[k] for k in ("eye_w_face", "iris_face") if m.get(k)]
    k = max(1.0, float(np.exp(np.mean(np.log(want)))))
    if k < 1 + tol:
        print("no fix needed", k); Image.fromarray(rgb).save(out, quality=95); return
    k = min(k, 1.15); P = dict(eye_sx=k, eye_sy=k)
    fixed = W.apply(big, pts, P)
    small = cv2.resize(fixed, (X1 - X0, Y1 - Y0), interpolation=cv2.INTER_AREA)
    msk = np.zeros(small.shape[:2], np.float32); f = max(3, int(0.1 * min(msk.shape)))
    msk[f:-f, f:-f] = 1; msk = cv2.GaussianBlur(msk, (0, 0), f / 2)[..., None]
    R = rgb.astype(np.float32); R[Y0:Y1, X0:X1] = small * msk + R[Y0:Y1, X0:X1] * (1 - msk)
    Image.fromarray(R.clip(0, 255).astype(np.uint8)).save(out, quality=95)
    print(f"eyefix k={k:.3f}", report("after", face_measure(np.array(Image.open(out).convert("RGB")))))

if __name__ == "__main__" and sys.argv[1] == "--fix":
    eyefix(sys.argv[2], sys.argv[3])
