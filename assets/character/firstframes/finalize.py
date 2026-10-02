#!/usr/bin/env python3
"""Crop/resize composites to 1280x720 first frames, build J-eyes from the real photo, run the gate, write board + gate.json."""
import sys, json, os
sys.path.insert(0, "/home/user/rewind-music-video/tools/likeness")
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import measure as MS
ROOT = "/home/user/rewind-music-video"; D = ROOT + "/assets/character/firstframes"
S = json.load(open(D + "/shots.json"))
META = {
 "J1": ("driving profile (lip-sync V1)", "GEN face (profile: real-photo paste-back impossible, MediaPipe/ORB cannot align a profile); conditioned on PXL_20260929_003030232"),
 "J1b": ("driving 3/4 from driver-side dash (lip-sync V1, restaged)", "REAL face pasted: PXL_20250908_195405539 (best eyes+glasses 3/4)"),
 "J2": ("mirror glance", "REAL face pasted: PXL_20250908_195405539"),
 "J3": ("reach/hold blank ID at window", "REAL face pasted: PXL_20250908_195352130"),
 "J5": ("performance center-lock, siren rim", "REAL face pasted: PXL_20260528_215628802"),
 "J5b": ("performance variation (rewind circle)", "REAL face pasted: IMG_20180610_074732"),
 "J6": ("driving 3/4 front through windshield (lip-sync V5)", "REAL face pasted: IMG_20180610_074732"),
 "J7m": ("running through grass, medium (no flashlight)", "GEN (v2 GRASS_RUN lineage) + likeness warp"),
 "J7w": ("running through grass, wide", "GEN (v2 lineage); face too small to measure"),
 "J8": ("alone in defense chair, singing softly", "REAL face pasted: PXL_20260929_001719023"),
 "J8b": ("turning around (ghosts added in code)", "REAL face pasted: IMG_20180610_073429"),
 "J9": ("driving determined, sirens behind", "REAL face pasted: PXL_20250908_195405539"),
 "J-eyes": ("ECU glasses (lens reflections added in code)", "REAL photo crop: PXL_20260528_215628802"),
}
def to169(img, face_y=None):
    h, w = img.shape[:2]; ch = int(w * 9 / 16)
    if ch > h:
        cw = int(h * 16 / 9); x0 = (w - cw) // 2; c = img[:, x0:x0 + cw]
    else:
        y0 = 0 if face_y is None else int(np.clip(face_y - 0.38 * ch, 0, h - ch)); c = img[y0:y0 + ch]
    return cv2.resize(c, (1280, 720), interpolation=cv2.INTER_AREA)
gate = {}
for sid in [k for k in META if k != "J-eyes"]:
    img = MS.load_rgb(f"{D}/pb/{sid}.jpg")
    lm = MS.landmarks(img); fy = float(lm[0][MS.GLABELLA, 1]) - 40 if lm else None
    out = to169(img, fy)
    cv2.imwrite(f"{D}/{sid}.jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
# J-eyes from the real photo
rgb = MS.load_rgb(ROOT + "/refs/jade/PXL_20260528_215628802.jpg"); pts = MS.landmarks(rgb)[0]
a, b = pts[MS.R_OUT, :2], pts[MS.L_OUT, :2]; c = (a + b) / 2; iod = np.linalg.norm(b - a)
ang = np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])); M = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), ang, 1280 / (3.3 * iod))
M[:, 2] += np.array([640, 360]) - c
e = cv2.warpAffine(rgb, M, (1280, 720), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
e = e * np.array([0.80, 0.88, 1.05]) * 0.72                      # cool night grade
yy, xx = np.mgrid[0:720, 0:1280]; v = np.clip(1 - 0.9 * (((xx - 640) / 820) ** 2 + ((yy - 330) / 470) ** 2), 0.08, 1)
e = np.clip(e * v[..., None], 0, 255).astype(np.uint8)
cv2.imwrite(f"{D}/J-eyes.jpg", cv2.cvtColor(e, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
# gate
for sid in META:
    m = None if sid == "J-eyes" else MS.measure(f"{D}/{sid}.jpg")
    if not m:
        gate[sid] = dict(measurable=False); continue
    ok, dev, br = MS.gate(m)
    src = S.get(sid, {}).get("src") if sid not in ("J1", "J7m", "J7w") else None
    rel = None
    if src:
        ms = MS.measure(ROOT + "/" + src)
        rel = {k: round(m[k] / ms[k] - 1, 4) for k in ["eye_w_face", "iris_face", "eye_open", "forehead", "upper_head"] if m.get(k) and ms.get(k)}
    gate[sid] = dict(measurable=True, yaw=m["yaw"], gate_ok=ok, dev_vs_real_mean=dev, dev_vs_source_photo=rel, brow=br,
                     face_px=m["face_px"], method=META[sid][1])
json.dump(gate, open(f"{D}/gate.json", "w"), indent=1, default=float)
# board
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22); FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
cols, tw, th = 3, 760, 428
ids = list(META); rows = (len(ids) + cols - 1) // cols
B = Image.new("RGB", (cols * (tw + 20) + 20, 70 + rows * (th + 110)), (20, 20, 22)); dr = ImageDraw.Draw(B)
dr.text((20, 20), "Jade first frames (1280x720) - REAL = her photo face pasted back pixel-exact; GEN = generated (v2 lineage), gated", font=F, fill=(240, 240, 240))
for i, sid in enumerate(ids):
    x = 20 + (i % cols) * (tw + 20); y = 70 + (i // cols) * (th + 110)
    im = Image.open(f"{D}/{sid}.jpg").resize((tw, th)); B.paste(im, (x, y))
    g = gate[sid]
    dr.text((x, y + th + 6), f"{sid}  {META[sid][0]}", font=F, fill=(255, 220, 90))
    dr.text((x, y + th + 36), META[sid][1][:95], font=FS, fill=(200, 200, 200))
    if g.get("measurable"):
        d = g["dev_vs_real_mean"]; s = " ".join(f"{k.split('_')[0]}{v * 100:+.0f}%" for k, v in d.items() if k in ("eye_w_face", "iris_face", "eye_open", "forehead", "upper_head"))
        tag = "PASS" if g["gate_ok"] else ("REAL-PHOTO (identity exact)" if g.get("dev_vs_source_photo") is not None else "FAIL")
        col = (120, 230, 120) if g["gate_ok"] or "REAL" in tag else (255, 110, 110)
        dr.text((x, y + th + 58), f"{tag}  yaw{g['yaw']:+.0f}  vs real mean: {s}", font=FS, fill=col)
        if g.get("dev_vs_source_photo"):
            dr.text((x, y + th + 78), "vs its source photo: " + " ".join(f"{k.split('_')[0]}{v * 100:+.0f}%" for k, v in g["dev_vs_source_photo"].items()), font=FS, fill=(170, 170, 170))
    else:
        dr.text((x, y + th + 58), "not measurable (profile / tiny / ECU) - visual check only", font=FS, fill=(200, 200, 120))
B.save(f"{D}/FIRSTFRAMES_BOARD.jpg", quality=88)
print(json.dumps({k: (v.get("gate_ok"), v.get("yaw")) for k, v in gate.items()}))
