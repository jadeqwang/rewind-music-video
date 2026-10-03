# fingertip.py: track her raised (twirling) index fingertip per roto frame with the MediaPipe pose landmarker
# (index-finger landmarks 19/20), for the cyan light-pen rewind arc. Writes meta.fingertip = [[x, y] | null, ...] at roto res.
#   python3 tools/jade2/fingertip.py R_rw1 [R_rw2 ...]
import os, sys, json, numpy as np, cv2
import mediapipe as mp
ROOT = os.path.abspath(os.path.dirname(__file__) + '/../..')
MODEL = ROOT + '/tools/roto/models/pose_landmarker_heavy.task'

def run(J):
    d = f'{ROOT}/assets/roto/{J}'; meta = json.load(open(d + '/meta.json'))
    opts = mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=MODEL), running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
    det = mp.tasks.vision.PoseLandmarker.create_from_options(opts)
    cap = cv2.VideoCapture(f"{ROOT}/{meta['src']}"); sfps = cap.get(cv2.CAP_PROP_FPS); frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    W, H = meta['w'], meta['h']; out = []
    for i in range(meta['frames']):
        f = cv2.resize(frames[min(len(frames) - 1, int(round(i / meta['fps'] * sfps)))], (W, H))
        r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)), int(i * 1000 / meta['fps']))
        tip = None
        if r.pose_landmarks:
            lm = r.pose_landmarks[0]
            c = [(lm[k].x * W, lm[k].y * H, lm[k].visibility) for k in (19, 20)]   # left / right index fingertip
            c = [p for p in c if p[2] > 0.3]
            if c: p = min(c, key=lambda p: p[1]); tip = [round(p[0], 1), round(p[1], 1)]   # the raised hand: the higher tip
        out.append(tip)
    # fill short gaps + light smoothing (3-tap) so the pen stroke is continuous
    xs = [p for p in out]; n = len(xs)
    for i in range(n):
        if xs[i] is None:
            a = next((xs[j] for j in range(i - 1, max(-1, i - 4), -1) if out[j]), None); b = next((xs[j] for j in range(i + 1, min(n, i + 4)) if out[j]), None)
            if a and b: xs[i] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
    sm = []
    for i in range(n):
        win = [xs[j] for j in range(max(0, i - 1), min(n, i + 2)) if xs[j]]
        sm.append([round(sum(p[0] for p in win) / len(win), 1), round(sum(p[1] for p in win) / len(win), 1)] if xs[i] and win else None)
    meta['fingertip'] = sm; json.dump(meta, open(d + '/meta.json', 'w'))
    print(J, sum(1 for p in sm if p), '/', n, 'frames tracked')

if __name__ == '__main__':
    for J in sys.argv[1:]: run(J)
