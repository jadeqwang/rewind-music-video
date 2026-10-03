#!/usr/bin/env python3
"""Objective checks for insert_them.py (we can't listen): re-separate 30-45 s of each variant with the same UVR model,
then measure f0 accuracy (pyin, cents vs target), cepstral distance to neighbouring sung vowels, BS.1770 momentary
loudness vs "show"/"and", and spectral-flux smoothness at the splice points. Writes analysis/them/verify.json + plot."""
import os, sys, json, subprocess, numpy as np, soundfile as sf, librosa
from scipy import signal
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, librosa.display
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000
D = os.path.join(ROOT, "assets/sound"); O = os.path.join(ROOT, "analysis/them"); E0 = 30.0
FILES = {"orig": "Rewind5_final.wav", "A": "Rewind5_final_v2A.wav", "B": "Rewind5_final_v2.wav", "C": "Rewind5_final_v2C.wav"}
V_ON = 37.8164
for k, f in FILES.items():
    sd = os.path.join(O, f"sep_{k}")
    if not os.path.exists(os.path.join(sd, "vocals.wav")):
        x, _ = sf.read(os.path.join(D, f), start=int(E0 * SR), stop=int(45 * SR), dtype="float32"); p = os.path.join(O, f"ex_{k}.wav"); sf.write(p, x, SR)
        subprocess.run([sys.executable, os.path.join(ROOT, "analysis/separate_mdx.py"), p, sd], check=True, capture_output=True); os.remove(p)
stem5 = sf.read(os.path.join(ROOT, "analysis/stems_v5/vocals.wav"))[0].mean(1)
sv = {k: sf.read(os.path.join(O, f"sep_{k}", "vocals.wav"))[0].mean(1) for k in FILES}
seg = lambda x, a, b, off=E0: x[int((a - off) * SR):int((b - off) * SR)]
cents = lambda f, r: 1200 * np.log2(f / r)


def pyin(x):
    y = librosa.resample(x, orig_sr=SR, target_sr=16000)
    f, _, _ = librosa.pyin(y, fmin=150, fmax=900, sr=16000, frame_length=1024, hop_length=80)
    return f  # 5 ms


def kweight(x):  # ITU-R BS.1770 K-weighting at 48 kHz
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x))


def lufs_m(x, a, b, off=E0):  # max momentary loudness (400 ms) with window centre in [a, b]
    y = kweight(x); vals = []
    for c in np.arange(a, b, 0.01):
        s = y[int((c - 0.2 - off) * SR):int((c + 0.2 - off) * SR)]; vals.append(-0.691 + 10 * np.log10(np.mean(s ** 2) + 1e-20))
    return float(max(vals))


def mfcc(x): return librosa.feature.mfcc(y=x.astype(np.float32), sr=SR, n_mfcc=20, n_fft=2048, hop_length=240)[1:].mean(1)


R = {}
shore = pyin(seg(stem5, 22.915, 23.30, 0))
ref_vowels = {"show": (37.40, 37.62, "line"), "and": (38.30, 38.45, "line"), "do": (38.80, 39.10, "line"),
              "Shore(B4)": (23.08, 23.24, "stem"), "dreamt1_eh(src)": (24.075, 24.18, "stem"), "dreamt2_eh": (158.06, 158.12, "stem")}
for k in ["A", "B", "C"]:
    tf = np.load(os.path.join(O, f"target_f0_{k}.npy"))
    x = sv[k]; r = {}
    f = pyin(seg(x, V_ON, V_ON + 0.40)); tt = V_ON + np.arange(len(f)) * 0.005
    tgt = np.interp(tt, tf[0], tf[1]); ok = np.isfinite(f) & (tt < V_ON + 0.36)
    ce = cents(f[ok], tgt[ok])
    r["f0_voiced_frac"] = round(float(ok.mean()), 2)
    r["f0_err_cents_median_abs"] = round(float(np.median(np.abs(ce))), 1); r["f0_err_cents_p90_abs"] = round(float(np.percentile(np.abs(ce), 90)), 1)
    sus = ok & (tt > V_ON + 0.18) & (tt < V_ON + 0.33)
    r["sustain_B_median_hz"] = round(float(np.median(f[sus])), 1); r["shore_B_median_hz"] = round(float(np.nanmedian(shore[int(0.18 / 0.005):int(0.33 / 0.005)])), 1)
    r["sustain_vs_shore_cents"] = round(float(cents(r["sustain_B_median_hz"], r["shore_B_median_hz"])), 1)
    r["sustain_vs_B4_cents"] = round(float(cents(r["sustain_B_median_hz"], 493.883)), 1)
    # cepstral distances: inserted ɛ (re-separated) vs reference vowels; baselines between natural vowels
    ins = mfcc(seg(x, V_ON + 0.03, V_ON + 0.20))
    refs = {n: mfcc(seg(x, a, b) if w == "line" else seg(stem5, a, b, 0)) for n, (a, b, w) in ref_vowels.items()}
    r["cep_dist_inserted_to"] = {n: round(float(np.linalg.norm(ins - v)), 1) for n, v in refs.items()}
    r["cep_dist_baseline"] = {"show-and": round(float(np.linalg.norm(refs["show"] - refs["and"])), 1),
                              "show-do": round(float(np.linalg.norm(refs["show"] - refs["do"])), 1),
                              "dreamt1-dreamt2": round(float(np.linalg.norm(refs["dreamt1_eh(src)"] - refs["dreamt2_eh"])), 1),
                              "Shore-show": round(float(np.linalg.norm(refs["Shore(B4)"] - refs["show"])), 1)}
    r["LUFS_M_vocal_stem"] = {"them": round(lufs_m(x, V_ON + 0.05, V_ON + 0.25), 1), "show": round(lufs_m(x, 37.38, 37.60), 1),
                              "and": round(lufs_m(x, 38.30, 38.45), 1), "do": round(lufs_m(x, 38.80, 39.05), 1)}
    # LUFS-M of the full mix around the word, before vs after
    r["LUFS_M_mix"] = {"before": round(lufs_m(sf.read(os.path.join(D, FILES["orig"]), start=int(E0 * SR), stop=int(45 * SR))[0].mean(1), V_ON, V_ON + 0.3), 1),
                       "after": round(lufs_m(sf.read(os.path.join(D, FILES[k]), start=int(E0 * SR), stop=int(45 * SR))[0].mean(1), V_ON, V_ON + 0.3), 1)}
    # splice smoothness: log-mel spectral flux (re-separated vocal) at our boundaries vs natural onsets in the line
    M = librosa.power_to_db(librosa.feature.melspectrogram(y=x.astype(np.float32), sr=SR, n_fft=1024, hop_length=240, n_mels=64))
    fl = np.maximum(0, np.diff(M, axis=1)).sum(0); ft = E0 + (np.arange(len(fl)) + 1) * 240 / SR
    pk = lambda t: float(fl[(ft > t - 0.02) & (ft < t + 0.02)].max())
    r["flux_ours"] = {n: round(pk(t), 0) for n, t in [("hiss_start", 37.718), ("vowel_on", V_ON), ("m_end", V_ON + 0.40)]}
    r["flux_natural_onsets"] = {n: round(pk(t), 0) for n, t in [("show_sh", 37.20), ("show_vowel", 37.36), ("and", 38.27), ("I", 38.47), ("do", 38.75)]}
    # clicks: >8 kHz energy of (v2 - original) per 2 ms vs the original's own HF energy there
    a_, _ = sf.read(os.path.join(D, FILES["orig"]), start=int(37.6 * SR), stop=int(39.4 * SR)); b_, _ = sf.read(os.path.join(D, FILES[k]), start=int(37.6 * SR), stop=int(39.4 * SR))
    hp = signal.butter(4, 8000, "high", fs=SR, output="sos"); dh = signal.sosfilt(hp, (b_ - a_).mean(1)); oh = signal.sosfilt(hp, a_.mean(1))
    w = 96; dd = np.sqrt(np.convolve(dh ** 2, np.ones(w) / w, "same")); od = np.sqrt(np.convolve(oh ** 2, np.ones(w) / w, "same"))
    r["max_HF_insert_over_mix_dB"] = round(float(20 * np.log10(dd.max() / np.median(od))), 1)
    # pitch purity of the B4 sustain: fundamental vs the A4-scoop region (430-460 Hz), cf. the real "Shore" (20-28 dB)
    def purity(y):
        w = y * np.hanning(len(y)); F = 20 * np.log10(np.abs(np.fft.rfft(w, 8 * len(w))) + 1e-9); fq = np.fft.rfftfreq(8 * len(w), 1 / SR)
        return round(float(F[(fq > 480) & (fq < 505)].max() - F[(fq > 430) & (fq < 460)].max()), 1)
    ins_w = sf.read(os.path.join(O, f"insert_{k}.wav"))[0].mean(1)
    r["sustain_purity_dB"] = {"insert": purity(ins_w[int((V_ON + 0.18 - 37.6) * SR):int((V_ON + 0.33 - 37.6) * SR)]),
                              "Shore_22.9": purity(seg(stem5, 23.095, 23.245, 0)), "Shore_156.9": purity(seg(stem5, 157.07, 157.22, 0))}
    R[k] = r
    print(k, json.dumps(r))
json.dump(R, open(os.path.join(O, "verify.json"), "w"), indent=1)

# plot: mix spectrogram before/after (A) + f0: target, measured inserted (re-separated), "Shore" (shifted to the slot)
fig, ax = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
a0, a1 = 37.0, 39.4
for i, (nm, k) in enumerate([("before (Rewind5_final)", "orig"), ("after (Rewind5_final_v2 = variant B)", "B")]):
    x = sf.read(os.path.join(D, FILES[k]), start=int(a0 * SR), stop=int(a1 * SR))[0].mean(1).astype(np.float32)
    S = librosa.amplitude_to_db(np.abs(librosa.stft(x, n_fft=2048, hop_length=240)), ref=1.0)
    librosa.display.specshow(S, sr=SR, hop_length=240, x_axis="time", y_axis="log", ax=ax[i], vmin=-50, vmax=25, cmap="magma"); ax[i].set_title(nm); ax[i].set_ylim(80, 12000)
ax2 = ax[2]
for k, c in [("orig", "#888"), ("A", "c"), ("B", "orange"), ("C", "lime")]:
    f = pyin(seg(sv[k], a0, a1)); tt = np.arange(len(f)) * 0.005
    ax2.plot(tt, 1200 * np.log2(f / 493.883), color=c, lw=1.2 if k != "orig" else 2, label=f"re-separated vocal {k}")
tf = np.load(os.path.join(O, "target_f0_B.npy"))
ax2.plot(tf[0] - a0, 1200 * np.log2(tf[1] / 493.883), "w--", lw=1.5, label="target (Shore contour)")
ax2.plot(np.arange(len(shore)) * 0.005 + V_ON - a0, 1200 * np.log2(shore / 493.883), color="m", ls=":", lw=2, label='"Shore" 22.915 s (shifted)')
ax2.set_facecolor("#111"); ax2.set_ylabel("cents re B4"); ax2.set_ylim(-1300, 300); ax2.axhline(0, color="#555", lw=0.5); ax2.legend(fontsize=8, loc="lower right")
for a_ in ax:
    for t in (37.718, V_ON, V_ON + 0.4): a_.axvline(t - a0, color="cyan", lw=0.7, ls="--")
plt.tight_layout(); plt.savefig(os.path.join(D, "them_insert_spectrogram_f0.png"), dpi=60)
