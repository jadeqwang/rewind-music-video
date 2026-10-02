# Fidelity ladder: the same J6 frame (t=76.9) at A (bone cel) | B (warm-skin cel) | C (drawn over her real face) | reference.
import cv2, numpy as np, json, sys, subprocess, os
R = os.path.abspath(os.path.dirname(__file__) + '/../..')
FI = int(sys.argv[1]) if len(sys.argv) > 1 else 54
fd = json.load(open(R + '/assets/roto/J6/face.json'))[FI]
pts = np.array(fd['jaw'] + fd['eye_L_upper'] + fd['eye_R_upper']); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
cx, cy = (x0 + x1) / 2 + 420, (y0 + y1) / 2 - 30; s = int(max(x1 - x0, 140) * 2.3)
def crop(im, cx, cy, s, S=520):
    pad = cv2.copyMakeBorder(im, 800, 800, 800, 800, cv2.BORDER_CONSTANT, value=(10, 10, 10)); x = int(cx - s / 2) + 800; y = int(cy - s / 2) + 800
    return cv2.resize(pad[y:y + s, x:x + s], (S, S), interpolation=cv2.INTER_AREA)
tiles = [crop(cv2.imread(f'{R}/render/out/ladder_{v}/t76_900.jpg'), cx, cy, s) for v in 'ABC']
ref = cv2.imread(R + '/refs/jade/IMG_20180610_074732_mr1528617091925.jpg')
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
FL = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=R + '/tools/roto/models/face_landmarker.task')))
r = FL.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(ref, cv2.COLOR_BGR2RGB))); h, w = ref.shape[:2]
P = np.array([(p.x * w, p.y * h) for p in r.face_landmarks[0]]); fx0, fy0 = P.min(0); fx1, fy1 = P.max(0)
k = (fx1 - fx0) / (x1 - x0)
tiles.append(crop(ref, (fx0 + fx1) / 2, (fy0 + fy1) / 2 - 30 * k, int(s * k)))
for t, l in zip(tiles, ['A  3-tone bone cel (current)', 'B  warm-skin cel, 5 tones', 'C  drawn over her real face', 'reference photo']): cv2.putText(t, l, (10, 28), 0, 0.7, (0, 230, 255), 2)
cv2.imwrite(R + '/render/out/likeness_ladder.jpg', np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 92]); print('wrote render/out/likeness_ladder.jpg')
