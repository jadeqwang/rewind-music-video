#!/usr/bin/env python3
"""Spectrogram comparison 0-8 s (original / variant / stem) + null test of the variant vs the original."""
import os, subprocess, sys, numpy as np, soundfile as sf, librosa, librosa.display
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000
TAG = sys.argv[1] if len(sys.argv) > 1 else ""
D = os.path.join(ROOT, "assets/sound")
def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-map", "0:a", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)
o = dec(os.path.join(ROOT, "Rewind (4).mp3")); v, _ = sf.read(os.path.join(D, f"Rewind_with_intro_sfx{TAG}.wav"), dtype="float32")
s, _ = sf.read(os.path.join(D, f"intro_sfx{TAG}.wav"), dtype="float32")
n7 = 7 * SR
print("lengths equal:", o.shape == v.shape, o.shape)
print("bit-identical after 7.0 s:", np.array_equal(o[n7:].view(np.uint32), v[n7:].view(np.uint32)))
d = v.astype(np.float64) - o
nz = np.nonzero(np.abs(d).max(1))[0]
print("last differing sample: %.4f s" % (nz[-1] / SR if len(nz) else -1), " max diff after 6.8 s:", np.abs(d[int(6.8*SR):]).max())
REF = np.abs(librosa.stft(o[:8*SR].mean(1), n_fft=2048, hop_length=256)).max()
fig, ax = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
for a, (name, x) in zip(ax, [("original", o[:8*SR]), ("variant (with intro SFX)", v[:8*SR]), ("SFX stem alone", np.pad(s, ((0, 8*SR - len(s)), (0, 0))))]):
    S = librosa.amplitude_to_db(np.abs(librosa.stft(x.mean(1), n_fft=2048, hop_length=256)), ref=REF)
    librosa.display.specshow(S, sr=SR, hop_length=256, x_axis="time", y_axis="log", ax=a, vmin=-85, vmax=0, cmap="magma")
    a.set_title(name)
    for t, lab in [(0.594, "scrub start"), (4.406, "scrub stop"), (6.78, "braam"), (7.0, "identical from here")]:
        a.axvline(t, color="cyan", lw=0.8, ls="--"); a.text(t + 0.03, 12000, lab, color="cyan", fontsize=8)
plt.tight_layout(); out = os.path.join(D, f"spectrogram_0-8s{TAG}.png"); plt.savefig(out, dpi=72); print(out)
