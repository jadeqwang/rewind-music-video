"""Lip-sync lag curves, measured the way the renderer plays a take: clipTime = t - t0 + lag.

For each lag in +-0.46 s, the clip's mouth-openness curve is resampled at (t - t0 + lag) for every song time t
inside the window the edit uses, and correlated with the vocal-stem RMS envelope (both high-passed). Two
independent openness metrics are reported: the anime-face-cascade mouth ROI (mouth.py) and the skin-blob +
mouth-interior colour metric (mouth_color.py). A lag is trusted when both curves peak together.

(score.py slides the curves inside the window instead, which drops edge samples; on short, rhythmic windows it
can pick the wrong one of two periodic peaks, e.g. sd06 v3: -0.33 s there, +0.29 s here, both metrics agreeing.)

  python3 lag_curve.py clip.mp4 SONG_T0 WIN_A WIN_B
"""
import sys, json, numpy as np, librosa
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mouth, mouth_color
FPS = 24
y, sr = librosa.load('/tmp/work/vocals.wav', sr=22050, mono=True)
hop = sr // FPS
env = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop, center=True)[0]
et = np.arange(len(env)) / FPS
def curve(v, t0, win, hp=True):
    v = np.asarray(v, float); ok = np.isfinite(v); v = np.where(ok, v, np.nanmedian(v))
    if hp: v = v - np.convolve(v, np.ones(12) / 12, mode='same')
    e = env - np.convolve(env, np.ones(12) / 12, mode='same') if hp else env
    ts = np.arange(int(win[0] * FPS), int(win[1] * FPS)) / FPS
    out = []
    for k in range(-11, 12):
        lag = k / FPS
        ci = np.clip(np.round((ts - t0 + lag) * FPS).astype(int), 0, len(v) - 1)
        out.append(round(float(np.corrcoef(v[ci], np.interp(ts, et, e))[0, 1]), 2))
    return out
f, t0, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
r = mouth.track(f)
face = np.array(r['open'], float) if r['hit'] >= 0.3 else None
col, _ = mouth_color.openness(f)
print('lags  ', ' '.join(f'{k/24:+.2f}' for k in range(-11, 12)))
if face is not None:
    print('face  ', ' '.join(f'{c:+.2f}' for c in curve(face, t0, (a, b))), f'(hit {r["hit"]:.2f})')
print('colour', ' '.join(f'{c:+.2f}' for c in curve(col, t0, (a, b))))
