import librosa, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, sys
fs = sys.argv[2:]; fig, ax = plt.subplots(len(fs),1, figsize=(12,2.6*len(fs)))
for a,f in zip(np.atleast_1d(ax), fs):
    y, sr = librosa.load(f, sr=48000)
    S = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048, hop_length=256)), ref=np.max)
    librosa.display.specshow(S, sr=sr, hop_length=256, x_axis="time", y_axis="log", ax=a, vmin=-80)
    fl = librosa.feature.spectral_flatness(y=y).mean(); rms = librosa.feature.rms(y=y)[0]
    a.set_title(f"{f}  flat={fl:.3f} peak={20*np.log10(np.abs(y).max()):.1f}dB rms={20*np.log10(rms.mean()):.1f}")
plt.tight_layout(); plt.savefig(sys.argv[1], dpi=70)
