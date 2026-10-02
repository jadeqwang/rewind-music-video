"""Score lip sync of a clip against the song's vocal stem.

score(clip_mouth_json, vocals_wav, song_t0) -> best lag (s), correlation at best lag, correlation at 0.
Positive lag = mouth moves LATER than the song's vocal.
"""
import json, sys
import numpy as np
import librosa


def vocal_env(vocals_wav, t0, dur, fps=24.0):
    v, sr = librosa.load(vocals_wav, sr=22050, mono=True, offset=max(0, t0 - 0.5), duration=dur + 1.0)
    hop = int(sr / fps / 4)
    rms = librosa.feature.rms(y=v, frame_length=1024, hop_length=hop)[0]
    tt = np.arange(len(rms)) * hop / sr + max(0, t0 - 0.5)
    ft = t0 + np.arange(int(dur * fps)) / fps
    return np.interp(ft, tt, rms)


def score(mouth, vocals_wav, t0, max_lag=0.5, window=None):
    fps = mouth["fps"]
    op = np.array(mouth["open"], dtype=float)
    if window is not None:
        a = max(0, int((window[0] - t0) * fps)); b = min(len(op), int((window[1] - t0) * fps))
        op = op[a:b]; t0 = t0 + a / fps
    dur = len(op) / fps
    env = vocal_env(vocals_wav, t0, dur, fps)
    n = min(len(op), len(env))
    op, env = op[:n], env[:n]
    # smooth both lightly; compare derivative-free normalized curves
    k = np.ones(3) / 3
    op = np.convolve(op, k, mode="same"); env = np.convolve(env, k, mode="same")
    op = (op - op.mean()) / (op.std() + 1e-9); env = (env - env.mean()) / (env.std() + 1e-9)
    best = (-9, 0)
    res = {}
    L = int(max_lag * fps)
    for lag in range(-L, L + 1):
        if lag >= 0:
            a, b = op[lag:], env[:n - lag]
        else:
            a, b = op[:n + lag], env[-lag:]
        c = float(np.mean(a * b))
        res[lag] = c
        if c > best[0]:
            best = (c, lag)
    return {"best_lag_s": best[1] / fps, "best_corr": round(best[0], 3), "corr_at_0": round(res[0], 3),
            "curve": {str(k / fps): round(v, 3) for k, v in res.items()}}


if __name__ == "__main__":
    m = json.load(open(sys.argv[1]))
    r = score(m, sys.argv[2], float(sys.argv[3]))
    print(json.dumps({k: v for k, v in r.items() if k != "curve"}))
