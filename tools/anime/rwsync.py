#!/usr/bin/env python3
"""'Rewind.' lip check (sustained word): mouth-open curve (lipsync.py --json 'mouth') vs voiced-band (250-2500 Hz) energy of the
vocal-stem slice. Reports the first sustained mouth opening ('WIND' vowel) and the closing, vs the vocal's onset/end, plus the
best lag of the two curves (positive = mouth LATE).  rwsync.py LIP.json SLICE.mp3"""
import sys, json, subprocess, numpy as np
d = json.load(open(sys.argv[1])); m = np.array(d["mouth"], float); fps = d.get("fps", 24)
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[2], "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(pcm, np.float32); sr = 16000
X = np.abs(np.fft.rfft(np.lib.stride_tricks.sliding_window_view(x, 1024)[::sr // int(fps)] * np.hanning(1024), axis=1))
f = np.fft.rfftfreq(1024, 1 / sr); band = (f > 250) & (f < 2500)
e = 10 * np.log10((X[:, band] ** 2).sum(1) + 1e-9); n = min(len(e), len(m)); e, m = e[:n], m[:n]
def segs(v, thr):
    on = v > thr; out = []; i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]: j += 1
            if j - i >= int(0.25 * fps): out.append((round(i / fps, 2), round(j / fps, 2)))
            i = j
        else: i += 1
    return out
ve = segs(e, e.max() - 12); ms = segs(m, 0.5 * np.percentile(m, 95))
mz = (m - m.mean()) / (m.std() + 1e-9); ez = (e - e.mean()) / (e.std() + 1e-9); L = int(0.8 * fps)
lags = [(k / fps, float(np.mean(mz[max(0, k):n + min(0, k)] * ez[max(0, -k):n - max(0, k)]))) for k in range(-L, L + 1)]
best = max(lags, key=lambda q: q[1])
print(json.dumps({"vocal_segments": ve, "mouth_open_segments": ms, "best_lag_s": round(best[0], 3), "r": round(best[1], 3),
                  "r_lag0": round(dict(lags)[0.0], 3)}))
