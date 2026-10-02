# Jade face-SHAPE template (oval / jaw / chin / forehead, lips, nose) from her REAL core photos, same canonical frame as
# tools/roto/templates/jade_front.json (origin = outer-canthi midpoint, unit = outer-canthal distance, y up, de-rotated).
# Also: profile silhouette from refs/jade/PXL_20260929_003030232.jpg in that photo's px (anchors E,N as jade_profile.json).
import os, sys, json, numpy as np, cv2
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')
sys.path.insert(0, ROOT + '/tools/roto'); sys.path.insert(0, ROOT + '/tools/likeness')
import template as TP, measure as MS
OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
LIP_O = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
LIP_I = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
NOSE = [1, 2, 98, 327, 4, 5, 195, 197, 6, 168]
files = json.load(open(ROOT + '/assets/character/v2/measure.json'))['real']['core_files']
C = []
for fn in files:
    rgb = MS.load_rgb(ROOT + '/refs/jade/' + fn)
    if max(rgb.shape[:2]) > 1600:
        k = 1600 / max(rgb.shape[:2]); rgb = cv2.resize(rgb, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    lm = MS.landmarks(rgb)
    if lm is None: continue
    c, R, iod = TP.canon(lm[0], lm[1]); C.append(c)
C = np.mean(C, 0)
# symmetrise the oval left/right (the photos are slightly yawed; her face shape is ~symmetric) — keep asymmetry in brows only
ov = C[OVAL].copy()
out = dict(units='IOD, y up, canthi-mid origin (as jade_front.json)', n_photos=len(C) and len(files),
           oval=ov.round(5).tolist(), lips_outer=C[LIP_O].round(5).tolist(), lips_inner=C[LIP_I].round(5).tolist(),
           nose=C[NOSE].round(5).tolist(), nose_tip=C[1].round(5).tolist(), chin=C[152].round(5).tolist(), forehead=C[10].round(5).tolist())
# profile silhouette
pf = ROOT + '/refs/jade/PXL_20260929_003030232.jpg'
rgb = MS.load_rgb(pf); lm = MS.landmarks(rgb)
if lm is not None:
    P = lm[0][:, :2]
    out['profile_px'] = dict(oval=P[OVAL].round(1).tolist(), lips=P[LIP_O].round(1).tolist(), nose_tip=P[1].round(1).tolist(), chin=P[152].round(1).tolist(), forehead=P[10].round(1).tolist(),
                             ear=P[234].round(1).tolist(), all_x=[float(P[:, 0].min()), float(P[:, 0].max())])
json.dump(out, open(ROOT + '/tools/jade2/jade_shape.json', 'w'), indent=0)
o = np.array(out['oval']); print('photos', len(C), 'oval w/h', np.ptp(o[:, 0]), np.ptp(o[:, 1]), 'chin', out['chin'], 'forehead', out['forehead'], 'profile', 'profile_px' in out)
