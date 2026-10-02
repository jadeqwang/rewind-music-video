#!/usr/bin/env python3
"""Remove the loud percussive hit(s) from the intro of "Rewind (4).mp3" (Suno can't do it), as an optional variant.

Method: per-bin spectral cap toward the pre-hit texture (STFT 2048/256, per channel). In the edit window every bin's
magnitude is capped at its 92nd percentile over a clean reference window (4.45-6.74 s: same kalimba ostinato / drone /
rain / 16th ticks, no hit) + 2 dB. Anything the hit adds above that is removed; content already in the reference
(kalimba, drone, rain, ticks) passes at gain 1. Cap strength fades out with weight w(t), then the original samples are
spliced back with a 20 ms crossfade, so the file is bit-identical after the window. The vocal stem is ~-61 dB in
6-12 s, so the mix is processed directly (re-summing separated stems would add separation artifacts).

Candidates (times from analysis):
  c1  06.78 impact, full   : sub boom (20-150 Hz, +45 dB, decays to ~10 s) + broadband roll 6.78-7.75 s
  c1b 06.78 roll only      : only >150 Hz, 6.76-8.0 s (keeps the sub swell / 'braam')
  (checked and rejected: the HPSS 'percussive' peaks at 9.66/10.02/10.49 s... are kalimba note attacks (800-4k), and the
   16th-note HF tick pulse 8-20 kHz runs through the whole intro; neither is a separate loud hit)
Usage: declick_intro.py [candidate for v2, default c1]
"""
import os, sys, subprocess, numpy as np, soundfile as sf, librosa
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000
D = os.path.join(ROOT, "assets/sound"); PV = os.path.join(D, "preview"); os.makedirs(PV, exist_ok=True)
NF, HOP = 2048, 256
def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-map", "0:a", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
song = dec(os.path.join(ROOT, "Rewind (4).mp3"))
seg = song[:16 * SR].astype(np.float64)
fr = np.fft.rfftfreq(NF, 1 / SR)
X = np.stack([librosa.stft(seg[:, c], n_fft=NF, hop_length=HOP) for c in range(2)])   # (2, F, T)
tt = librosa.frames_to_time(np.arange(X.shape[-1]), sr=SR, hop_length=HOP)
def ramp(t, a, b): return np.clip((t - a) / (b - a), 0, 1)

def cap_gain(ref_win, fmask, w):
    r = (tt >= ref_win[0]) & (tt < ref_win[1])
    ref = np.percentile(np.abs(X[:, :, r]), 92, axis=-1, keepdims=True) * 10 ** (2 / 20)
    g = np.minimum(1, ref / (np.abs(X) + 1e-12))
    g = minimum_filter1d(g, 3, axis=-1); g = uniform_filter1d(g, 3, axis=-1); g = uniform_filter1d(g, 3, axis=1)
    g = g ** (fmask[None, :, None] * w[None, None, :])
    return g

def hpss_gain(fmask, w, att_db=12):
    g = np.ones(X.shape)
    for c in range(2):
        Hm, Pm = librosa.decompose.hpss(np.abs(X[c]), margin=2.0, mask=True)   # soft masks
        g[c] = Hm + Pm * 10 ** (-att_db / 20) + (1 - Hm - Pm)
    return g ** (fmask[None, :, None] * w[None, None, :])

lo = lambda f0, f1: np.clip((np.log2(np.maximum(fr, 1)) - np.log2(f0)) / np.log2(f1 / f0), 0, 1)   # 0 below f0 -> 1 above f1
CANDS = {
  "c1":  dict(name="06.78_impact_full", win=(6.70, 10.6),
              g=lambda: cap_gain((4.45, 6.74), np.ones_like(fr), ramp(tt, 6.70, 6.76) * (1 - ramp(tt, 8.6, 10.4)))),
  "c1b": dict(name="06.78_roll_only", win=(6.70, 8.3),
              g=lambda: cap_gain((4.45, 6.74), lo(120, 180), ramp(tt, 6.70, 6.76) * (1 - ramp(tt, 7.6, 8.1)))),
}

def apply(keys):
    G = np.ones(X.shape)
    for k in keys: G = G * CANDS[k]["g"]()
    y = np.stack([librosa.istft(X[c] * G[c], hop_length=HOP, length=len(seg)) for c in range(2)], 1)
    a = min(CANDS[k]["win"][0] for k in keys); b = max(CANDS[k]["win"][1] for k in keys)
    out = song.copy(); A, B, xf = int(a * SR), int(b * SR), int(0.02 * SR)
    fade = np.ones(B - A); fade[:xf] = np.linspace(0, 1, xf); fade[-xf:] = np.linspace(1, 0, xf)
    out[A:B] = (seg[A:B] * (1 - fade[:, None]) + y[A:B] * fade[:, None]).astype(np.float32)
    return out, b

stem, _ = sf.read(os.path.join(D, "intro_sfx.wav"), dtype="float32")
def add_sfx(x):
    x = x.copy(); x[:len(stem)] = (x[:len(stem)].astype(np.float64) + stem).astype(np.float32); return x
def mp3(x, path, secs=None):
    xx = x[:int(secs * SR)] if secs else x
    if secs: xx = xx.copy(); n = int(0.3 * SR); xx[-n:] *= np.linspace(1, 0, n)[:, None]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "320k", path],
                   input=xx.astype(np.float32).tobytes(), check=True)

def rms(x): return 20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean()) + 1e-12)
mp3(add_sfx(song), os.path.join(PV, "00_reference_original_plus_sfx_0-14s.mp3"), 14)
results = {}
for k in ["c1", "c1b"]:
    out, b = apply([k]); results[k] = (out, b)
    mp3(add_sfx(out), os.path.join(PV, f"{k}_{CANDS[k]['name']}_0-14s.mp3"), 14)
    w = slice(int(CANDS[k]["win"][0] * SR), int(b * SR))
    print(f"{k} {CANDS[k]['name']}: window {CANDS[k]['win']}, removed {rms(song[w]-out[w]):.1f} dBFS rms, "
          f"window rms {rms(song[w]):.1f} -> {rms(out[w]):.1f} dB")

pick = sys.argv[1:] or ["c1"]
out, b = apply(pick)
mix = add_sfx(out)
tp = 20 * np.log10(np.abs(signal.resample_poly(mix[:int(14 * SR)].astype(np.float64), 4, 1, axis=0)).max())
sf.write(os.path.join(D, "Rewind_v2_intro_clean.wav"), mix, SR, subtype="FLOAT")
mp3(mix, os.path.join(D, "Rewind_v2_intro_clean.mp3"))
n = int(np.ceil(b * SR))
nz = np.nonzero(np.abs(mix.astype(np.float64) - song).max(1))[0]
print("v2 =", pick, "| edit ends %.3f s | last differing sample %.4f s | bit-identical after: %s | len equal %s | TP 0-14s %.2f dBTP"
      % (b, nz[-1] / SR, np.array_equal(mix[n:].view(np.uint32), song[n:].view(np.uint32)), mix.shape == song.shape, tp))

# before/after spectrogram 0-14 s
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, librosa.display
REF = np.abs(librosa.stft(song[:14 * SR].mean(1), n_fft=2048, hop_length=256)).max()
rows = [("original", song), ("v2: " + "+".join(CANDS[k]["name"] for k in pick) + " removed + intro SFX", mix), ("removed (original - edited song)", song - out)]
fig, ax = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
for a, (nm, x) in zip(ax, rows):
    S = librosa.amplitude_to_db(np.abs(librosa.stft(x[:14 * SR].mean(1).astype(np.float32), n_fft=2048, hop_length=256)), ref=REF)
    librosa.display.specshow(S, sr=SR, hop_length=256, x_axis="time", y_axis="log", ax=a, vmin=-85, vmax=0, cmap="magma"); a.set_title(nm)
    for t in (6.78, 9.66, b): a.axvline(t, color="cyan", lw=0.8, ls="--")
plt.tight_layout(); plt.savefig(os.path.join(D, "spectrogram_v2_intro_clean_0-14s.png"), dpi=60)
