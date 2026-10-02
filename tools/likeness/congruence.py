#!/usr/bin/env python3
"""Head-vs-body pose congruence for composites (real face pasted onto a generated body).

  python3 tools/likeness/congruence.py IMG [IMG ...]

head yaw/pitch/roll: MediaPipe Face Landmarker transformation matrix (measure.pose_angles; yaw<0 = nose toward
image-left).  torso yaw: MediaPipe Pose Landmarker world landmarks, shoulder line (11 = her left, 12 = her right)
yaw = atan2(dz, dx) mapped to the same sign convention; shoulder roll from the 2-D shoulder line.
Reports delta = head_yaw - torso_yaw. Heads naturally turn on the torso, but in a composite a |delta| > 12 deg
(threshold 12) or head and torso turned to opposite sides by > ~12 deg each, reads as uncanny -> flag.
"""
import sys, os, math, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS

_pose = {}


def pose_model():
    if "p" not in _pose:
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        p = os.path.join(MS.MODELS, "pose_landmarker_full.task")
        if not os.path.exists(p):
            import urllib.request
            urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task", p)
        _pose["p"] = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=p)))
    return _pose["p"]


def check(path):
    import mediapipe as mp
    rgb = MS.load_rgb(path); h, w = rgb.shape[:2]
    out = dict(file=os.path.basename(path))
    lm = MS.landmarks(rgb)
    if lm:
        y, p, r = MS.pose_angles(lm[1]); out.update(head_yaw=round(y, 1), head_pitch=round(p, 1), head_roll=round(r, 1))
    res = pose_model().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if res.pose_world_landmarks:
        W = res.pose_world_landmarks[0]; L, R = W[11], W[12]           # her left / right shoulder
        # x grows to image-right, z grows away from camera. Her right shoulder is image-left when facing camera.
        dx, dz = L.x - R.x, L.z - R.z
        out["torso_yaw"] = round(math.degrees(math.atan2(dz, dx)), 1)  # >0: her left shoulder further away -> turned to her left? (see sign calibration)
        I = res.pose_landmarks[0]
        out["shoulder_roll"] = round(math.degrees(math.atan2((I[11].y - I[12].y) * h, (I[11].x - I[12].x) * w)), 1)
        out["shoulder_vis"] = round(min(I[11].visibility, I[12].visibility), 2)
    if "head_yaw" in out and "torso_yaw" in out:
        out["delta"] = round(out["head_yaw"] - out["torso_yaw"], 1)
        opp = out["head_yaw"] * out["torso_yaw"] < 0 and min(abs(out["head_yaw"]), abs(out["torso_yaw"])) > 12
        out["congruent"] = bool(abs(out["delta"]) <= 12 and not opp)
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(check(p)))
