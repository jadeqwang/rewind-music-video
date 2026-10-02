#!/usr/bin/env python3
"""Lip-sync check: mouth-open signal (MediaPipe landmarks) vs vocal-stem envelope.

  python3 tools/likeness/lipsync.py CLIP.mp4 VOCALS.wav --audio-start 13.15 [--win 0.3 7.97] [--maxlag 0.5] [--json out.json]

  --audio-start  song time (s) that corresponds to video t=0 (the start of the reference_audios slice)
  --win A B      analysis window in VIDEO time (default: whole clip), e.g. the sung part
Mouth signal: inner-lip gap (13-14) / outer-canthal distance, per frame (frames with no face are interpolated).
Audio: RMS of the vocal stem in 1/fps hops, log-compressed, light smoothing. Both are z-scored inside the window.
Reports Pearson r at lag 0 and the best lag in [-maxlag, +maxlag] (positive lag = mouth LATE vs audio),
plus the fraction of frames with a detected face.
"""
import sys, os, json, argparse, subprocess
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS


def mouth_signal(path):
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 24
    sig = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        lm = MS.landmarks(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        if lm is None:
            sig.append(np.nan); continue
        p = lm[0]
        sig.append(np.linalg.norm(p[13, :2] - p[14, :2]) / np.linalg.norm(p[MS.R_OUT, :2] - p[MS.L_OUT, :2]))
    s = np.array(sig, float); det = np.isfinite(s).mean()
    if np.isfinite(s).sum() >= 2:
        idx = np.arange(len(s)); s = np.interp(idx, idx[np.isfinite(s)], s[np.isfinite(s)])
    return s, fps, det


def audio_env(wav, start, n, fps, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(n / fps + 0.5), "-i", wav, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = sr / fps
    env = np.array([np.sqrt(np.mean(a[int(i * hop):int((i + 1) * hop)] ** 2) + 1e-9) for i in range(n)])
    env = np.log(env + 1e-4)
    return np.convolve(env, np.ones(3) / 3, mode="same")


def z(x):
    return (x - x.mean()) / (x.std() + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("wav"); ap.add_argument("--audio-start", type=float, required=True)
    ap.add_argument("--win", type=float, nargs=2); ap.add_argument("--maxlag", type=float, default=0.5); ap.add_argument("--json")
    a = ap.parse_args()
    m, fps, det = mouth_signal(a.clip)
    e = audio_env(a.wav, a.audio_start, len(m), fps)
    i0, i1 = (0, len(m)) if not a.win else (int(a.win[0] * fps), min(len(m), int(a.win[1] * fps)))
    L = int(a.maxlag * fps); best = (-9, 0)
    rs = {}
    for lag in range(-L, L + 1):
        j0, j1 = i0 + lag, i1 + lag                  # mouth index = audio index + lag
        if j0 < 0 or j1 > len(m):
            continue
        r = float(np.corrcoef(z(m[j0:j1]), z(e[i0:i1]))[0, 1]); rs[lag] = r
        if r > best[0]:
            best = (r, lag)
    out = dict(clip=a.clip, fps=fps, frames=len(m), face_detect_frac=round(float(det), 3), window_s=[i0 / fps, i1 / fps],
               r_lag0=round(rs.get(0, float("nan")), 3), best_r=round(best[0], 3), best_lag_s=round(best[1] / fps, 3),
               mouth_open_range=[round(float(np.percentile(m, 5)), 3), round(float(np.percentile(m, 95)), 3)])
    print(json.dumps(out))
    if a.json:
        json.dump(dict(out, mouth=m.round(4).tolist(), env=e.round(4).tolist()), open(a.json, "w"))


if __name__ == "__main__":
    main()
