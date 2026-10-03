#!/usr/bin/env python3
"""Insert the sung word "them" into "I reach for my ID to show (them) and I do" (v5 ~37.7-38.25 s) of Rewind5_final.wav.

No voice model: the word is built from her own sung phonemes on the v5 vocal stem (analysis/stems_v5/vocals.wav):
  /ð/  : the whispered "th" hiss of "The" (A: reprise 147.665-147.815, C: verse-1 13.765-13.875)
  /ɛm/ : the ɛ + m of "dreamt" before the t (A/C: verse 1 24.065-24.345, B: reprise 158.055-158.420)
WORLD vocoder (pyworld): the spectral envelope (formants) + aperiodicity are kept, and they are time-stretched to the slot
(ɛ 0.22 s on the beat 37.816, m 0.18 s). f0 = the measured contour of "Shore" (22.92-23.30 s: A4 scoop -> B4,
moved to the same times relative to the vowel onset). Then: an octave-smoothed tilt EQ toward "show"/"Shore",
level matched to "show", a synthetic room tail calibrated to the stem's own post-word decay, and the L/R balance of "show".
The word is ADDED to the full mix (the gap has no vocal), so the file is bit-identical outside [W0, W1].
Usage: insert_them.py [A|B|C ...]   (default: all; B = the master Rewind5_final_v2, A/C -> Rewind5_final_v2A/C)
"""
import os, sys, json, subprocess, numpy as np, soundfile as sf, pyworld as pw, librosa
from scipy import signal
from scipy.ndimage import uniform_filter1d
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000
D = os.path.join(ROOT, "assets/sound"); PV = os.path.join(D, "preview")
voc, _ = sf.read(os.path.join(ROOT, "analysis/stems_v5/vocals.wav")); vm = voc.mean(1)
mix, _ = sf.read(os.path.join(D, "Rewind5_final.wav"), dtype="float32")
T = json.load(open(os.path.join(ROOT, "analysis/timing_v5.json")))
beats = np.array(T["beats"])
FP = 5.0  # WORLD frame period, ms

SRC = {"A": dict(th=(147.665, 147.815), eh=(24.065, 24.19), m=(24.19, 24.345)),
       "B": dict(th=(147.665, 147.815), eh=(158.055, 158.13), m=(158.13, 158.42)),
       "C": dict(th=(13.765, 13.875), eh=(24.065, 24.19), m=(24.19, 24.345))}
V_ON = float(beats[np.argmin(np.abs(beats - 37.8))])     # vowel on the beat (37.816), like "show"/"Shore"
TH_LEN, EH_LEN, M_LEN = 0.11, 0.22, 0.18
SHORE = (22.915, 23.30)                                  # "Shore" vowel: onset on the beat 22.915
W0, W1 = 37.60, 39.40
LEVEL_TRIM_DB = 1.0   # first pass measured LUFS-M (re-separated vocal) 1 dB under "show"/"and" -> +1 dB
MASTER = "B"          # best f0 accuracy / sustain purity (verify_them.py) -> Rewind5_final_v2; A, C -> Rewind5_final_v2A/C                                    # edit window (everything outside is untouched)


def seg(t0, t1, x=vm): return x[int(round(t0 * SR)):int(round(t1 * SR))].astype(np.float64)


def world(x):
    f0, t = pw.harvest(x, SR, f0_floor=150, f0_ceil=800, frame_period=FP)
    return f0, pw.cheaptrick(x, f0, t, SR), pw.d4c(x, f0, t, SR)


# ---- target f0: the "Shore" contour (cents relative to B4 kept exactly), interpolated over unvoiced frames
f0s, _, _ = world(seg(SHORE[0] - 0.05, SHORE[1] + 0.05))
f0s = f0s[int(0.05 * 1000 / FP):]
ts = np.arange(len(f0s)) * FP / 1000
vv = f0s > 0
f0s = np.interp(ts, ts[vv], f0s[vv])
SHORE_REF = float(np.median(f0s[(ts > 0.18) & (ts < 0.33)]))        # sustained B4 part


def build(key):
    S = SRC[key]
    eh, m = seg(*S["eh"]), seg(*S["m"])
    f0e, spe, ape = world(np.concatenate([eh, m]))
    ne = int(len(eh) / SR * 1000 / FP)
    n_out_e, n_out_m = int(EH_LEN * 1000 / FP), int(M_LEN * 1000 / FP)
    # time map out-frame -> source frame (piecewise linear: ɛ part, m part)
    src_idx = np.r_[np.linspace(0, ne - 1, n_out_e), np.linspace(ne, len(f0e) - 1, n_out_m)]
    lo_ = np.floor(src_idx).astype(int); fr_ = (src_idx - lo_)[:, None]; hi_ = np.minimum(lo_ + 1, len(f0e) - 1)
    sp = np.exp(np.log(spe[lo_] + 1e-16) * (1 - fr_) + np.log(spe[hi_] + 1e-16) * fr_)
    ap = ape[lo_] * (1 - fr_) + ape[hi_] * fr_
    n = len(sp); to = np.arange(n) * FP / 1000
    f0 = np.interp(to, ts, f0s)                     # same timing relative to the vowel onset as "Shore"
    # source voicing: keep m voiced; unvoiced only where the source had no periodicity at the very edges
    y = pw.synthesize(np.ascontiguousarray(f0), np.ascontiguousarray(sp), np.ascontiguousarray(ap), SR, frame_period=FP)
    y = y[:int((EH_LEN + M_LEN) * SR)]
    # amplitude shape: 12 ms fade-in (the hiss covers the onset), m decays to 0 over its last 60 ms
    env = np.ones(len(y)); a = int(0.012 * SR); env[:a] = np.linspace(0, 1, a) ** 2
    r = int(0.06 * SR); env[-r:] *= np.linspace(1, 0, r) ** 1.5
    y *= env
    # /ð/ hiss
    th = seg(*S["th"]); th = signal.resample_poly(th, int(TH_LEN * 1000), int(len(th) / SR * 1000)) if abs(len(th) / SR - TH_LEN) > 0.005 else th
    th = th[:int(TH_LEN * SR)]; tw = np.ones(len(th)); k = int(0.025 * SR); tw[:k] = np.linspace(0, 1, k); tw[-int(0.02 * SR):] = np.linspace(1, 0.35, int(0.02 * SR))
    th *= tw
    return y, th, f0, to


def tilt_eq(y, ref):
    """octave-smoothed spectral tilt correction of y toward ref (clamped +-4 dB), 300 Hz - 12 kHz."""
    nf = 4096
    P = lambda x: np.mean(np.abs(librosa.stft(x.astype(np.float32), n_fft=nf, hop_length=512)) ** 2, axis=1)
    fr = np.fft.rfftfreq(nf, 1 / SR)
    lf = np.log2(np.maximum(fr, 20))
    def oct_smooth(p):
        out = np.empty_like(p)
        for i, l in enumerate(lf): out[i] = p[np.abs(lf - l) <= 0.5].mean()
        return 10 * np.log10(out + 1e-20)
    d = oct_smooth(P(ref)) - oct_smooth(P(y))
    band = (fr > 300) & (fr < 12000); d -= np.median(d[band])
    g = np.clip(np.where(band, d, np.interp(fr, fr[band], d[band])), -4, 4)
    Y = librosa.stft(y.astype(np.float32), n_fft=nf, hop_length=512)
    return librosa.istft(Y * 10 ** (g[:, None] / 20), hop_length=512, length=len(y)).astype(np.float64), g


def rms_db(x): return 10 * np.log10(np.mean(x ** 2) + 1e-20)


SHOW_BODY = seg(37.40, 37.62)
ref_tilt = np.concatenate([SHOW_BODY, seg(23.08, 23.24)])   # "show" body + "Shore" on B4
show_lr = np.sqrt((voc[int(37.40 * SR):int(37.62 * SR)] ** 2).mean(0)); show_lr = show_lr / show_lr.mean()
# post-word tail of "show" in the stem: level 60-250 ms after its end relative to its body
TAIL_REL = rms_db(seg(37.74, 37.93)) - rms_db(SHOW_BODY)
rng = np.random.default_rng(7)


def room(n_sec=1.1, rt60=0.9):
    L = int(n_sec * SR); t = np.arange(L) / SR
    ir = rng.standard_normal((L, 2)) * np.exp(-6.91 * t / rt60)[:, None]
    ir[:int(0.015 * SR)] = 0                                  # pre-delay
    ir = signal.sosfilt(signal.butter(2, [250, 6000], "band", fs=SR, output="sos"), ir, axis=0)
    return ir / np.sqrt((ir ** 2).sum(0).mean())


IR = room()


def make(key):
    y, th, f0, to = build(key)
    y, g = tilt_eq(y, ref_tilt)
    # level: ɛ body (first 0.2 s after onset) = "show" body
    body = y[int(0.03 * SR):int(0.20 * SR)]
    gain = 10 ** ((rms_db(SHOW_BODY) + LEVEL_TRIM_DB - rms_db(body)) / 20); y *= gain
    # hiss level: keep its ratio to the following vowel in the source ("The"+"night"), capped to "show"'s sh -6 dB
    th_src_ratio = rms_db(seg(*SRC[key]["th"])) - rms_db(seg(SRC[key]["th"][1] + 0.03, SRC[key]["th"][1] + 0.2))
    th *= 10 ** ((rms_db(SHOW_BODY) + min(th_src_ratio, rms_db(seg(37.20, 37.34)) - rms_db(SHOW_BODY) - 6) - rms_db(th)) / 20)
    dry = np.zeros(int((W1 - W0) * SR))
    o_th = int((V_ON - TH_LEN + 0.012 - W0) * SR); o_v = int((V_ON - W0) * SR)
    dry[o_th:o_th + len(th)] += th
    dry[o_v:o_v + len(y)] += y
    end = o_v + len(y)
    # room tail: wet gain so that the word's own tail (60-250 ms after its end) sits at TAIL_REL under its body
    best = None
    # ducked room: the sources already carry their own room sound, and full-time reverb smears the A4 scoop into the B4
    # sustain (measured: A4-region only 2 dB under the fundamental vs 20-28 dB on the real "Shore"), so the wet is held
    # at 10 % while the word sounds and opens over its last 80 ms -> it adds only the release tail.
    duck = np.ones(len(dry)); duck[:end] = 0.1
    r0 = end - int(0.08 * SR); duck[r0:end] = np.linspace(0.1, 1, end - r0)
    WET = np.stack([signal.fftconvolve(dry, IR[:, c])[:len(dry)] for c in range(2)], 1) * duck[:, None]
    for wg in np.linspace(0.05, 2.0, 79):
        wet = WET * wg
        out = dry[:, None] * show_lr[None] + wet
        rel = rms_db(out[end + int(0.06 * SR):end + int(0.25 * SR)].mean(1)) - rms_db(out[o_v + int(0.03 * SR):o_v + int(0.2 * SR)].mean(1))
        if best is None or abs(rel - TAIL_REL) < abs(best[1] - TAIL_REL): best = (wg, rel, out)
    wg, rel, out = best
    fo = int(0.25 * SR); out[-fo:] *= np.linspace(1, 0, fo)[:, None]; out[:int(0.005 * SR)] = 0
    v2 = mix.copy(); a0 = int(W0 * SR)
    v2[a0:a0 + len(out)] = (mix[a0:a0 + len(out)].astype(np.float64) + out).astype(np.float32)
    info = dict(variant=key, src=SRC[key], vowel_on=V_ON, wet_gain=round(float(wg), 3), tail_rel_dB=round(float(rel), 1), target_tail_rel_dB=round(float(TAIL_REL), 1),
                tilt_eq_dB_range=[round(float(g.min()), 1), round(float(g.max()), 1)])
    return v2, out, f0, to, info


def mp3(x, path, a=None, b=None):
    xx = x[int(a * SR):int(b * SR)].copy() if a is not None else x
    if a is not None: k = int(0.2 * SR); xx[:k] *= np.linspace(0, 1, k)[:, None]; xx[-k:] *= np.linspace(1, 0, k)[:, None]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "320k", path],
                   input=xx.astype(np.float32).tobytes(), check=True)


if __name__ == "__main__":
    keys = sys.argv[1:] or ["A", "B", "C"]
    os.makedirs(os.path.join(ROOT, "analysis/them"), exist_ok=True)
    mp3(mix, os.path.join(PV, "them_before_30-45s.mp3"), 30, 45)
    INFO = {"target_f0_shore_B_median_hz": SHORE_REF, "target_cents_vs_B4": 1200 * np.log2(SHORE_REF / 493.883), "show_tail_rel_dB": TAIL_REL}
    for k in keys:
        v2, out, f0, to, info = make(k)
        nz = np.nonzero(np.any(v2.view(np.uint32) != mix.view(np.uint32), axis=1))[0]
        info["null"] = dict(len_equal=v2.shape == mix.shape, first_diff_s=round(nz[0] / SR, 4), last_diff_s=round(nz[-1] / SR, 4),
                            identical_outside_window=bool(nz[0] >= int(W0 * SR) and nz[-1] < int(W1 * SR)))
        name = "Rewind5_final_v2" if k == MASTER else f"Rewind5_final_v2{k}"
        sf.write(os.path.join(D, name + ".wav"), v2, SR, subtype="FLOAT")
        if k == MASTER: mp3(v2, os.path.join(D, name + ".mp3"))
        mp3(v2, os.path.join(PV, f"them_after_30-45s.mp3" if k == MASTER else f"them_after_{k}_30-45s.mp3"), 30, 45)
        sf.write(os.path.join(ROOT, f"analysis/them/insert_{k}.wav"), out.astype(np.float32), SR, subtype="FLOAT")
        np.save(os.path.join(ROOT, f"analysis/them/target_f0_{k}.npy"), np.stack([to + V_ON, f0]))
        INFO[k] = info; print(json.dumps(info))
    json.dump(INFO, open(os.path.join(ROOT, "analysis/them/build.json"), "w"), indent=1, default=float)
