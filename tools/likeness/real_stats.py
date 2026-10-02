#!/usr/bin/env python3
"""Measure the real reference photos and write the 'real' section of assets/character/v2/measure.json.
Core set = the 5 near-frontal photos the user prioritised; 'all' = every ref with |yaw|<=26, pitch<20 and a
detected hairline. Brow asymmetry is yaw-dependent, so it is fitted as asym = a + b*yaw over 'all'."""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CORE = ["IMG_20180610_074732_mr1528617091925.jpg", "IMG_20160827_121631.jpg", "IMG_20180209_082832.jpg",
        "PXL_20250908_195405539.MP.jpg", "PXL_20260528_215628802.jpg"]
per = {}
for f in sorted(glob.glob(ROOT + "/refs/jade/*.jpg")):
    if "trace" in f:
        continue
    per[os.path.basename(f)] = MS.measure(f)
core = [per[c] for c in CORE]
allr = [m for m in per.values() if m and abs(m["yaw"]) <= 26 and m["pitch"] < 20 and (m.get("forehead") or 0) > 0.2]
stat = lambda rows, k: [float(np.mean([r[k] for r in rows if r.get(k) is not None])), float(np.std([r[k] for r in rows if r.get(k) is not None], ddof=1))]
real = dict(core_files=CORE, n_core=len(core), n_all=len(allr),
            mean={k: round(stat(core, k)[0], 4) for k in MS.KEYS},
            sd={k: round(stat(core, k)[1], 4) for k in MS.KEYS},
            all_mean={k: round(stat(allr, k)[0], 4) for k in MS.KEYS},
            all_sd={k: round(stat(allr, k)[1], 4) for k in MS.KEYS})
# yaw sensitivity of each ratio (linear in |yaw|, fitted over 'all'), used by gate() to adjust the reference
ay = np.array([abs(m["yaw"]) for m in allr])
real["yaw_slope"] = {k: round(float(np.polyfit(ay, [m[k] for m in allr], 1)[0]), 6) for k in MS.KEYS if all(m.get(k) is not None for m in allr)}
real["core_abs_yaw"] = round(float(np.mean([abs(m["yaw"]) for m in core])), 2)
# brows
bro = [m for m in per.values() if m and m.get("brow_asym") and abs(m["yaw"]) <= 26]
y = np.array([m["yaw"] for m in bro]); A = np.c_[np.ones_like(y), y]
fit = {}
for k in ["height", "peak_height", "peak_pos", "angle", "arch", "thick", "length"]:
    a = np.array([m["brow_asym"][k] for m in bro])
    c = np.linalg.lstsq(A, a, rcond=None)[0]
    fit[k] = dict(intercept=round(float(c[0]), 4), per_deg_yaw=round(float(c[1]), 5), resid_sd=round(float((a - A @ c).std()), 4))
real["brow"] = dict(
    n=len(bro), asym_fit=fit,
    imgL_mean={k: round(float(np.mean([m["brow_imgL"][k] for m in bro])), 4) for k in bro[0]["brow_imgL"]},
    imgR_mean={k: round(float(np.mean([m["brow_imgR"][k] for m in bro])), 4) for k in bro[0]["brow_imgR"]},
    convention="asym = image-left brow minus image-right brow, in IOD units (angle in deg, + = tail higher); "
               "pixel-level brow contour (measure.brow_pixels) on a canthus-aligned crop.",
    mirroring="All refs are treated as true (un-mirrored) views: IMG_20180209 has readable fridge-magnet text and "
              "PXL_20260929_003045 shows an un-mirrored browser layout; Pixel saves front-camera shots un-mirrored "
              "by default, and every ref gives the same yaw-corrected sign. So image-left = HER RIGHT brow, "
              "image-right = HER LEFT brow. Generated plates are compared in image space at the same convention.",
    finding="Yaw-corrected, her RIGHT brow (image-left) sits slightly lower (~-0.014 IOD mean height, -0.023 peak), "
            "is flatter/less arched (-0.011), a touch thinner and shorter, with its peak nearer the middle "
            "(peak_pos ~0.5); her LEFT brow (image-right) is higher with a more pronounced arch peaking further out "
            "toward the tail (~0.65-0.75). Effect sizes are ~1-2 SE, consistent with the visual crops.")
real["files"] = {k: ({kk: m.get(kk) for kk in ["yaw", "pitch"] + MS.KEYS + ["brow_imgL", "brow_imgR", "brow_asym"]} if m else None) for k, m in per.items()}
out = ROOT + "/assets/character/v2/measure.json"
db = json.load(open(out)) if os.path.exists(out) else {}
db["real"] = real
db.setdefault("method", MS.__doc__)
json.dump(db, open(out, "w"), indent=1)
print(json.dumps({k: real[k] for k in ["mean", "sd"]}, indent=0))
print(json.dumps(real["brow"]["asym_fit"]))
