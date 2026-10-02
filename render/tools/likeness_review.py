# Likeness review: renderer Jade (1080p) | her real reference photo | the shot's first-frame still, same-scale face crops.
# usage: python3 render/tools/likeness_review.py   → render/out/likeness_review.jpg
import cv2, json, subprocess, os, sys, numpy as np
R = os.path.abspath(os.path.dirname(__file__) + '/../..')
OUT = R + '/render/out/likeness'
SHOTS = [  # (time, roto, shot t0, cam dx, zoom0, zoom1, shot dur, ref photo, first frame)
    *[(t, 'J1', 13.452, 0, 1, 1, 7.668, 'refs/jade/PXL_20260929_003030232.jpg', 'assets/character/firstframes/J1.jpg') for t in (14.4, 18.4, 20.3)],
    *[(t, 'J6', 73.55, 420, 1.0, 1.03, 7.02, 'refs/jade/IMG_20180610_074732_mr1528617091925.jpg', 'assets/character/firstframes/J6.jpg') for t in (74.3, 76.9, 79.6)],
]
S = 420
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
FL = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=R + '/tools/roto/models/face_landmarker.task'), num_faces=1))
MANUAL = {'refs/jade/PXL_20260929_003030232.jpg': (330, 760, 1000, 1000), 'assets/character/firstframes/J1.jpg': (680, 150, 165, 165)}
def detect(im):
    r = FL.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: return None
    h, w = im.shape[:2]; xs = [p.x * w for p in r.face_landmarks[0]]; ys = [p.y * h for p in r.face_landmarks[0]]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

def face_crop(im, box=None, k=2.6):
    h, w = im.shape[:2]
    if box is None: box = detect(im) or (w // 3, h // 4, w // 3, w // 3)
    x, y, bw, bh = [float(v) for v in box]; cx, cy, s = x + bw / 2, y + bh * 0.55, max(bw, bh) * k
    x0, y0 = int(cx - s / 2), int(cy - s / 2)
    pad = cv2.copyMakeBorder(im, 800, 800, 800, 800, cv2.BORDER_CONSTANT, value=(10, 10, 10))
    return cv2.resize(pad[y0 + 800:y0 + 800 + int(s), x0 + 800:x0 + 800 + int(s)], (S, S), interpolation=cv2.INTER_AREA)

times = ','.join(str(t) for t, *_ in SHOTS)
V2 = '--v2' in sys.argv
V3 = '--v3' in sys.argv
if not V3: subprocess.run(['node', R + '/render/render.mjs', '--stills', times, '--out', OUT, '--query', 'jadev1'], check=True, cwd=R + '/render', stdout=subprocess.DEVNULL)
else: OUT1 = R + '/render/out/likeness_v2save'
if V2: subprocess.run(['node', R + '/render/render.mjs', '--stills', times, '--out', OUT + '_v2'], check=True, cwd=R + '/render', stdout=subprocess.DEVNULL)
rows = []
for (t, rid, t0, dx, z0, z1, dur, ref, ff) in SHOTS:
    im = cv2.imread((f'{OUT1}' if V3 else f'{OUT}') + f'/t{t:.3f}'.replace('.', '_', 1) + '.jpg')
    meta = json.load(open(f'{R}/assets/roto/{rid}/meta.json')); fd = json.load(open(f'{R}/assets/roto/{rid}/face.json'))
    fi = min(meta['frames'] - 1, int((t - t0) * meta['fps'] + 1e-3)); f = fd[fi] or {}
    pts = sum([f.get(k, []) for k in ('jaw', 'eye_L_upper', 'eye_R_upper', 'eye_near_upper', 'brow_L', 'brow_R', 'brow_near')], [])
    if f.get('N'): pts.append(f['N'])
    pts = np.array(pts, float); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    z = z0 + (z1 - z0) * min(1, (t - t0) / dur)
    X = lambda x: (x - 960) * z + 960 + dx; Y = lambda y: (y - 540) * z + 540
    cxp, cyp = X((x0 + x1) / 2), Y((y0 + y1) / 2); bw = (220 if f.get('mode') == 'profile' else max(x1 - x0, 140)) * z
    box = (cxp - bw / 2, cyp - bw * 0.55, bw, bw)
    if V2:
        im2 = cv2.imread(f'{OUT}_v2/t{t:.3f}'.replace('.', '_', 1) + '.jpg')
        tiles = [face_crop(im, box, 2.4), face_crop(im2, box, 2.4), face_crop(cv2.imread(f'{R}/{ref}'), MANUAL.get(ref))]; labs = [(f'v2 {rid} t={t}' if V3 else f'v1 {rid} t={t}'), (f'v3 {rid} t={t}' if V3 else f'v2 {rid} t={t}'), 'reference photo']
    else:
        tiles = [face_crop(im, box, 2.4), face_crop(cv2.imread(f'{R}/{ref}'), MANUAL.get(ref)), face_crop(cv2.imread(f'{R}/{ff}'), MANUAL.get(ff))]; labs = [f'render {rid} t={t}', 'reference photo', f'first frame {rid}']
    for tile, lab in zip(tiles, labs):
        cv2.putText(tile, lab, (10, 26), 0, 0.7, (0, 230, 255), 2)
    rows.append(np.hstack(tiles))
name = ('likeness_review_v3.jpg' if '--v3' in sys.argv else 'likeness_review_v2.jpg') if V2 else 'likeness_review.jpg'
cv2.imwrite(R + '/render/out/' + name, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])
print('wrote render/out/' + name)
