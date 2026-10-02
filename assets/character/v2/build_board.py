#!/usr/bin/env python3
"""Builds REVIEW_BOARD_v2.jpg and the 'outputs' section of v2/measure.json."""
import sys, os, json
sys.path.insert(0, "/home/user/rewind-music-video/tools/likeness")
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import measure as MS, compare as CP
ROOT = "/home/user/rewind-music-video"; D = ROOT + "/assets/character/v2"
db = json.load(open(D + "/measure.json")); R = db["real"]["mean"]; SD = db["real"]["sd"]
K = [("eye_w_face", "eye w/face"), ("iris_face", "iris/face"), ("eye_open", "eye open"), ("forehead", "forehead"),
     ("upper_head", "upper head"), ("forehead_w", "forehead w"), ("jaw_w", "jaw w")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17); FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
except Exception:
    F = FB = FS = ImageFont.load_default()
fix = [("REAL (PXL_20250908)", ROOT + "/refs/jade/PXL_20250908_195405539.MP.jpg", None),
       ("G original", ROOT + "/assets/character/DRIVER_PLATE_y27.jpg", None),
       ("G_fixed: warp only (CHOSEN)", D + "/cands/G_warp.jpg", None),
       ("edit only (gpt-image-2)", D + "/cands/G_edit_b.jpg", None),
       ("edit + warp", D + "/cands/G_edit_b_warp.jpg", None)]
outputs = {}
W = 2400; tw = 420; th = 560
board = Image.new("RGB", (W, 4300), (236, 234, 230)); dr = ImageDraw.Draw(board)
dr.text((30, 20), "Jade likeness v2 - G fix + rebuilt sheet. Numbers: measured value (deviation vs REAL core-5 mean). Gate: eyes/forehead within ~5%, never smaller eyes.", font=FB, fill=(20, 20, 20))
y = 70; x = 30
for lab, p, _ in fix:
    t = Image.fromarray(CP.crop(p)); board.paste(t, (x, y))
    m = MS.measure(p); ok, dev, br = MS.gate(m)
    outputs[os.path.relpath(p, ROOT)] = dict(m={k: m.get(k) for k in ["yaw"] + MS.KEYS}, gate_ok=ok, dev=dev, brow=br)
    dr.text((x, y + th + 6), lab, font=F, fill=(0, 0, 0))
    for j, (k, nm) in enumerate(K):
        v = m.get(k)
        s = f"{nm}: {v:.3f}" + (f" ({(v / R[k] - 1) * 100:+.1f}%)" if "REAL" not in lab else "") if v is not None else f"{nm}: -"
        col = (0, 0, 0) if "REAL" in lab or v is None or abs(v / R[k] - 1) <= 0.05 else ((180, 0, 0) if v < R[k] else (0, 110, 0))
        dr.text((x, y + th + 30 + 20 * j), s, font=FS, fill=col)
    x += tw + 40
dr.text((30, y + th + 185), "REAL core-5 mean +- sd: " + "  ".join(f"{nm} {R[k]:.3f}+-{SD[k]:.3f}" for k, nm in K), font=FS, fill=(0, 0, 120))
note = ("Fix method: deterministic landmark warp (tools/likeness/warp.py): eyes scaled about their centres (ellipse falloff, glasses rims move <1 px, brows untouched) "
        "and the whole region above the brow line (forehead+cranium+hair) scaled up as one unit -> hairline rises because the head grows. "
        "Edit-only changed her face/expression; warp-only keeps G's identity, so G_fixed = warp only.")
dr.text((30, y + th + 210), note[:190], font=FS, fill=(60, 60, 60)); dr.text((30, y + th + 230), note[190:], font=FS, fill=(60, 60, 60))
mir = ("Brows / mirroring: refs treated as un-mirrored (readable text in IMG_20180209, un-mirrored browser in PXL_20260929_003045; Pixel saves selfies un-mirrored). "
       "Image-left = her RIGHT brow: yaw-corrected it sits ~0.014 IOD lower, flatter, peak mid-brow; her LEFT brow (image-right) is higher with an arch peaking toward the tail. "
       "Warp never moves brows; gate checks the asymmetry z-score vs the real yaw fit.")
dr.text((30, y + th + 250), mir[:200], font=FS, fill=(60, 60, 60)); dr.text((30, y + th + 270), mir[200:], font=FS, fill=(60, 60, 60))
y = y + th + 310
sheet = [("FACE_SHEET", None), ("EXPRESSIONS", None), ("TURNAROUND", 4), ("DRIVER_PLATE", None), ("WINDOW_ID", None), ("GRASS_RUN", None)]
pos = [(30, y), (1215, y), (30, y + 870), (1215, y + 870), (30, y + 1740), (1215, y + 1740)]
for (nm, nt), (px, py) in zip(sheet, pos):
    p = f"{D}/{nm}.jpg"
    im = Image.open(p).convert("RGB"); im.thumbnail((1155, 770)); board.paste(im, (px, py))
    ms = MS.measure_multi(p, nt); lines = []; outputs[f"assets/character/v2/{nm}.jpg"] = []
    for j, e in enumerate(ms):
        m = e["m"]
        if not m: continue
        ok, dev, br = MS.gate(m)
        outputs[f"assets/character/v2/{nm}.jpg"].append(dict(face=j, m={k: m.get(k) for k in ["yaw"] + MS.KEYS}, gate_ok=ok, dev=dev, brow=br))
        lines.append(f"f{j} yaw{m['yaw']:+.0f} {'PASS' if ok else 'FAIL'}: " + " ".join(f"{nm2} {dev.get(k, 0) * 100:+.1f}%" for k, nm2 in K[:5] if k in dev))
    dr.text((px, py + im.size[1] + 4), nm + (" (profile/back views not measurable)" if nm in ("FACE_SHEET", "TURNAROUND") else ""), font=F, fill=(0, 0, 0))
    for j, l in enumerate(lines[:4]):
        dr.text((px, py + im.size[1] + 26 + 18 * j), l, font=FS, fill=(0, 100, 0) if "PASS" in l else (170, 0, 0))
board = board.crop((0, 0, W, pos[-1][1] + 870))
board.save(ROOT + "/assets/character/REVIEW_BOARD_v2.jpg", quality=90)
db["outputs"] = outputs
db["selection"] = {"DRIVER_PLATE": "cands/G_warp.jpg (G + warp)", "FACE_SHEET": "cands/FS1_w.jpg", "EXPRESSIONS": "cands/EX1_w.jpg",
                   "TURNAROUND": "cands/TU1_w.jpg", "WINDOW_ID": "cands/WI1_w.jpg", "GRASS_RUN": "../firstframes/cands/J7m.jpg + warp (flashlight removed per director review)"}
json.dump(db, open(D + "/measure.json", "w"), indent=1, default=float)
print("ok")
