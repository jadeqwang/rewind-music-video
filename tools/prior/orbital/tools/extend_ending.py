"""Let the song's last chord ring out instead of being cut off at 237.76 s.

The final hit (≈234.5 s, an A chord: A1/A2 + E2) decays to about −46 dB and the file stops while it is
still ringing. This builds a natural tail:
  1. freeze   — average STFT magnitude of the sustained chord just after the attack (235.0–235.6 s),
                resynthesised with random phase (stereo, slightly decorrelated) into a steady texture;
  2. envelope — level-matched to the original where they cross-fade (from ≈236.0 s), then a slow
                exponential decay that gets steeper, so the note lingers ~1 s longer and fades over ~5 s;
  3. damping  — a time-varying low-pass so the highs die first, like a real sustained note;
  4. space    — a synthetic reverb (decaying filtered noise, RT60 ≈ 3 s) on the tail;
  5. the original is kept untouched up to the cross-fade.
Writes media/audio/Orbital_Sunrise_extended.wav (48 kHz) and a before/after spectrogram for review.
"""
import pathlib, subprocess, numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "Orbital_Sunrise.mp3"
OUT = ROOT / "media" / "audio" / "Orbital_Sunrise_extended.wav"
SR = 48000
FREEZE = (235.0, 235.6)      # sustained chord window (after the attack)
XF0, XF1 = 236.0, 236.9      # cross-fade from the original into the tail
TAIL = 6.2                   # seconds of new material after XF0
RT60 = 3.0


def load(path):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy()


def stft(x, n=8192, hop=1024):
    w = np.hanning(n)
    frames = [np.fft.rfft(x[i:i + n] * w) for i in range(0, len(x) - n, hop)]
    return np.array(frames)


def freeze_texture(y, secs, rng, n=8192, hop=1024):
    """Random-phase resynthesis of the averaged magnitude spectrum (per channel, partly shared phase)."""
    a, b = int(FREEZE[0] * SR), int(FREEZE[1] * SR)
    mags = [np.abs(stft(y[c, a:b], n, hop)).mean(0) for c in range(2)]
    frames = int(secs * SR / hop) + 8 + 2 * n // hop       # extra frames: the overlap-add warm-up is discarded
    w = np.hanning(n)
    out = np.zeros((2, frames * hop + n))
    norm = np.zeros(frames * hop + n)
    for f in range(frames):
        shared = rng.uniform(0, 2 * np.pi, len(mags[0]))
        for c in range(2):
            ph = .75 * shared + .25 * rng.uniform(0, 2 * np.pi, len(mags[c]))
            fr = np.fft.irfft(mags[c] * np.exp(1j * ph), n) * w
            out[c, f * hop:f * hop + n] += fr
        norm[f * hop:f * hop + n] += w ** 2
    out /= np.maximum(norm, 1e-6)
    return out[:, n:n + int(secs * SR)]                     # skip the first window (normalisation blows up there)


def lowpass_timevarying(x, f_start, f_end):
    """One-pole low-pass whose cutoff glides exponentially from f_start to f_end over the signal."""
    n = x.shape[1]
    fc = f_start * (f_end / f_start) ** (np.arange(n) / n)
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x)
    for c in range(2):
        s = 0.0
        xc, yc = x[c], y[c]
        for i in range(n):
            s = (1 - a[i]) * xc[i] + a[i] * s
            yc[i] = s
    return y


def reverb_ir(rng, secs=4.0):
    n = int(secs * SR)
    t = np.arange(n) / SR
    env = 10 ** (-3 * t / RT60)                      # −60 dB at RT60
    ir = rng.standard_normal((2, n)) * env
    # darker late reverb: simple low-pass by moving average growing with time
    k = 24
    ir = np.array([np.convolve(ch, np.ones(k) / k, mode="same") for ch in ir])
    ir[:, :int(.012 * SR)] *= np.linspace(0, 1, int(.012 * SR))
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True)) * .5


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def main():
    rng = np.random.default_rng(7)
    y = load(SRC)
    n0 = y.shape[1]
    T0 = 235.8                                   # the frozen chord starts underneath the still-ringing original
    t0 = int(T0 * SR)
    tex = freeze_texture(y, TAIL + 1.0, rng)[:, :int((TAIL + (XF0 - T0)) * SR)]
    t = np.arange(tex.shape[1]) / SR
    # level: 6 dB under the original around T0, then it takes over as the original falls away
    ref = y[:, t0 - int(.1 * SR):t0 + int(.1 * SR)]
    g0 = 10 ** ((rms_db(ref) - 6 - rms_db(tex[:, int(.2 * SR):int(.6 * SR)])) / 20)
    fade_in = np.sin(np.pi / 2 * np.clip(t / 1.2, 0, 1))
    db = np.where(t < 2.0, -6.0 * t, -12.0 - 13.0 * (t - 2.0))       # linger, then fall
    env = 10 ** (db / 20) * fade_in
    Ttot = tex.shape[1] / SR
    env *= .5 * (1 + np.cos(np.pi * np.clip((t - (Ttot - 1.3)) / 1.3, 0, 1)))
    tail = lowpass_timevarying(tex * g0 * env, 6000.0, 1100.0)
    out_len = t0 + tail.shape[1]
    out = np.zeros((2, out_len), dtype=np.float64)
    orig = y.astype(np.float64).copy()
    fe0 = int(.25 * SR)                          # the original keeps ringing to its end; only de-click the cut
    orig[:, -fe0:] *= np.cos(np.linspace(0, np.pi / 2, fe0)) ** 2
    out[:, :n0] = orig
    out[:, t0:] += tail
    # a room on the last chord and the tail, brought in after the hit
    a = int(234.3 * SR)
    ir = reverb_ir(rng)
    wet = np.array([np.convolve(out[c, a:], ir[c], mode="full")[:out_len - a] for c in range(2)])
    wet_gain = 10 ** ((rms_db(out[:, a:a + int(1.5 * SR)]) - rms_db(wet[:, :int(1.5 * SR)]) - 10) / 20)
    ramp = np.clip((np.arange(out_len - a) / SR - .3) / 1.5, 0, 1)
    out[:, a:] += wet * wet_gain * ramp
    # final safety: fade the very end to zero, clip guard
    fe = int(.4 * SR)
    out[:, -fe:] *= np.cos(np.linspace(0, np.pi / 2, fe)) ** 2
    peak = np.abs(out).max()
    if peak > .999:
        out *= .999 / peak
    OUT.parent.mkdir(parents=True, exist_ok=True)
    import soundfile as sf
    sf.write(str(OUT), out.T.astype(np.float32), SR, subtype="PCM_24")
    print(f"wrote {OUT}: {out_len / SR:.2f} s (was {n0 / SR:.2f} s)")
    # review: spectrogram of the last 12 s, original vs extended
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
        for k, (sig, name) in enumerate([(y, "original"), (out, "extended")]):
            s0 = int(230 * SR); seg = sig[:, s0:].mean(0)
            ax[k].specgram(seg, NFFT=4096, Fs=SR, noverlap=3072, cmap="magma", vmin=-140)
            ax[k].set_ylim(0, 6000); ax[k].set_title(name); ax[k].set_ylabel("Hz")
        ax[1].set_xlabel("seconds after 230 s")
        fig.tight_layout(); fig.savefig(OUT.with_suffix(".png"), dpi=80)
        # level curve
        fig, ax = plt.subplots(figsize=(12, 3))
        for sig, name in [(y, "original"), (out, "extended")]:
            s0 = int(230 * SR); seg = sig[:, s0:].mean(0); hop = SR // 20
            lv = [20 * np.log10(np.sqrt(np.mean(seg[i:i + hop] ** 2)) + 1e-9) for i in range(0, len(seg) - hop, hop)]
            ax.plot(230 + np.arange(len(lv)) / 20, lv, label=name)
        ax.set_ylim(-90, -5); ax.legend(); ax.set_ylabel("dBFS"); fig.tight_layout(); fig.savefig(OUT.with_name("ending_levels.png"), dpi=80)
    except Exception as e:
        print("plot failed", e)


if __name__ == "__main__":
    main()
