"""Lip-sync score that works for profiles and push-ins, where the anime face cascade fails.

Per frame: find the face as the largest skin-coloured blob, take the lower part of its box as the mouth
region, and count dark-red mouth-interior pixels there (normalised by the box area). The openness curve
and the vocal-stem envelope are both high-passed, then cross-correlated over the window the edit uses.

  python3 mouth_color.py clip.mp4 SONG_T0 WIN_A WIN_B
"""
import json
import sys

import cv2
import librosa
import numpy as np

FPS = 24


def openness(path):
    cap = cv2.VideoCapture(path)
    vals, boxes = [], []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        skin = ((h <= 22) & (s >= 25) & (s <= 130) & (v >= 150)).astype(np.uint8)
        skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(skin, 8)
        if n < 2:
            vals.append(np.nan); boxes.append(None); continue
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        x, y, w, hh, area = st[i]
        if area < 1500:
            vals.append(np.nan); boxes.append(None); continue
        # mouth region: lower half of the face blob, inset horizontally
        y0, y1 = y + int(hh * 0.5), y + hh + int(hh * 0.08)
        x0, x1 = x + int(w * 0.1), x + int(w * 0.9)
        sub = hsv[y0:y1, x0:x1]
        m = (((sub[..., 0] <= 8) | (sub[..., 0] >= 170)) & (sub[..., 1] > 90) & (sub[..., 2] > 40) & (sub[..., 2] < 190))
        vals.append(m.sum() / max(1.0, w * hh))
        boxes.append((int(x), int(y), int(w), int(hh)))
    return np.array(vals, float), boxes


def score(vals, t0, win, vocals="/tmp/work/vocals.wav", max_lag=0.3):
    ok = np.isfinite(vals)
    if ok.mean() < 0.5:
        return {"error": f"face blob in only {ok.mean():.0%} of frames"}
    v = np.where(ok, vals, np.nanmedian(vals))
    y, sr = librosa.load(vocals, sr=22050, mono=True)
    hop = sr // FPS
    env = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop, center=True)[0]
    et = np.arange(len(env)) / FPS

    def hp(x, w=12):
        return x - np.convolve(x, np.ones(w) / w, mode="same")

    tt = np.arange(len(v)) / FPS + t0
    ts = tt[(tt >= win[0]) & (tt <= win[1])]
    res = []
    for k in range(-int(max_lag * FPS), int(max_lag * FPS) + 1):
        lag = k / FPS
        ci = np.clip(np.round((ts - t0 + lag) * FPS).astype(int), 0, len(v) - 1)
        c = np.corrcoef(hp(v)[ci], np.interp(ts, et, hp(env)))[0, 1]
        res.append((lag, float(c)))
    best = max(res, key=lambda r: r[1])
    c0 = [c for l, c in res if abs(l) < 1e-9][0]
    return {"lag": round(best[0], 3), "corr": round(best[1], 3), "corr0": round(c0, 3), "face": round(float(ok.mean()), 2)}


if __name__ == "__main__":
    vals, _ = openness(sys.argv[1])
    print(json.dumps(score(vals, float(sys.argv[2]), (float(sys.argv[3]), float(sys.argv[4])))))
