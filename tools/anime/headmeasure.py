"""Measure anime heads on turnaround sheets: crop head boxes (in 1536x1024 sheet coords), upscale, run measure()."""
import sys, json; sys.path.insert(0, "/home/user/rewind-music-video/tools/likeness")
import numpy as np, cv2
from measure import measure, real_ref
from PIL import Image
def heads(path, boxes, up=3):
    im = np.array(Image.open(path).convert("RGB")); res = []
    for b in boxes:
        t = cv2.resize(im[b[1]:b[3], b[0]:b[2]], None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
        res.append(measure(t))
    return res
if __name__ == "__main__":
    K = ["yaw", "eye_w_face", "iris_face", "eye_open", "forehead", "face_hw", "forehead_w", "temple_w", "jaw_w", "lowjaw_w", "chin_w", "chin_angle", "upper_head"]
    boxes = json.loads(sys.argv[1])
    for p in sys.argv[2:]:
        for i, m in enumerate(heads(p, boxes)):
            print(p.split('/')[-1], i, {k: m.get(k) for k in K} if m else None)
