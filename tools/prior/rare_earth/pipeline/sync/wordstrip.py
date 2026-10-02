"""Visual lip-sync check: face crops at each sung word onset, for several candidate lags.

  python3 wordstrip.py clip.mp4 song_t0 out.jpg [face_box x,y,w,h]
Rows = words sung inside the clip window; columns = lag candidates (clip shown at song time + lag).
"""
import json
import sys

import cv2
import numpy as np

WORDS = "/tmp/work/lyrics_words_v3.json"
LAGS = [-0.25, -0.125, 0.0, 0.125, 0.25]


def main(clip, t0, out, box=None):
    cap = cv2.VideoCapture(clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    dur = len(frames) / fps
    words = [w for w in json.load(open(WORDS)) if t0 <= w["t"] < t0 + dur - 0.05]
    H, W = frames[0].shape[:2]
    if box is None:
        # face box from the anime cascade on the middle frame, else center crop
        cas = cv2.CascadeClassifier("/tmp/work/lbpcascade_animeface.xml")
        best = None
        for f in frames[::6]:
            det = cas.detectMultiScale(cv2.equalizeHist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)), 1.06, 3, minSize=(40, 40))
            for b in det:
                if best is None or b[2] > best[2]:
                    best = b
        if best is not None:
            x, y, w, h = best
            box = (int(x + 0.15 * w), int(y + 0.35 * h), int(0.7 * w), int(0.6 * h))
        else:
            box = (W // 3, H // 4, W // 3, H // 2)
    x, y, w, h = box
    th = 96
    tw = max(1, int(w * th / max(1, h)))
    rows = []
    for wd in words:
        tiles = []
        for lag in LAGS:
            fi = int(round((wd["t"] - t0 + lag) * fps))
            fi = max(0, min(len(frames) - 1, fi))
            crop = frames[fi][max(0, y):y + h, max(0, x):x + w]
            crop = cv2.resize(crop, (tw, th))
            cv2.putText(crop, f"{lag:+.2f}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
            tiles.append(crop)
        label = np.zeros((th, 150, 3), np.uint8)
        cv2.putText(label, wd["word"][:14], (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(label, f"{wd['t']:.2f}", (4, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        rows.append(np.hstack([label] + tiles))
    img = np.vstack(rows) if rows else np.zeros((10, 10, 3), np.uint8)
    cv2.imwrite(out, img)
    print(json.dumps({"words": len(words), "box": list(map(int, box))}))


if __name__ == "__main__":
    b = tuple(int(v) for v in sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    main(sys.argv[1], float(sys.argv[2]), sys.argv[3], b)
