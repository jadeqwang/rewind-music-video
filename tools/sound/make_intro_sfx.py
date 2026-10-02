#!/usr/bin/env python3
"""Optional A/B variant: subtle sound design for the cold-open hook (0-6.8 s) of "Rewind (4).mp3" (or --song/--timing for v5:
  make_intro_sfx.py --song "Rewind (5).mp3" --timing analysis/timing_v5.json --tag 5  -> intro_sfx5.wav, Rewind5_with_intro_sfx.wav).

Layers (all derived from the song itself unless --el-whir):
  freeze  0.00-0.594  reversed synthetic-reverb tail of the gunshot noise burst (43.24-43.48 s), E-tuned comb -> "suspended" swell
  chatter 0.594-4.406 granular reverse scrub along the H1_scrub playhead (226.7 s -> 13.45 s, ~x56), band-limited 350 Hz-7 kHz (song-derived),
                      grain pitch factor rising x2.5 -> x9, level ramps up, hard stop at bt(9)=4.406 + tiny transport clunk
  whir    0.594-4.406 synthetic tape-transport motor (glide 70->330 Hz, flutter) + rising tape hiss
            (--el-whir: ElevenLabs music-v2 'rw_b' rising whir instead)
Kalimba protection: STFT spectral side-chain -- in 220-3000 Hz (tapered 130 Hz / 6.5 kHz) the stem is held >= MARGIN dB under the song, bin by bin.
Output: stem (7.0 s), full mix = original decoded samples + stem in 0-7 s, -1 dBTP on the touched region, untouched after.
"""
import sys, os, subprocess, json, numpy as np, soundfile as sf
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SR = 48000
OUT = os.path.join(ROOT, "assets/sound")
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--el-whir", action="store_true")
ap.add_argument("--song", default="Rewind (4).mp3", help="input master (relative to repo root or absolute)")
ap.add_argument("--timing", default="analysis/timing.json", help="timing JSON on the input's timeline")
ap.add_argument("--tag", default=None, help="output name tag; default '' (v4) -> intro_sfx{tag}.wav, Rewind{tag}_with_intro_sfx.wav")
ap.add_argument("--stem-only", action="store_true", help="write only the stem (used by declick_intro.py pipelines)")
ARGS = ap.parse_args()
EL_WHIR = ARGS.el_whir
TAG = (ARGS.tag or "") + ("_elwhir" if EL_WHIR else "")
MARGIN = 6.0   # dB under the song in the kalimba band
_T = json.load(open(os.path.join(ROOT, ARGS.timing)))
_bt = _T["beats"]; _sec = {s_["name"]: s_ for s_ in _T["sections"]}
_ev = lambda ty, n=1: [e for e in _T["events"] if e["type"] == ty][n - 1]["t"]
T_FREEZE_END, T_STOP = _bt[1], _bt[9]          # bt(1), bt(9)  (v4: 0.5939, 4.4056)
SRC_FROM, SRC_TO = _sec["end"]["start"] - 0.5, _sec["verse1"]["start"]   # H1_scrub playhead (v4: 226.7 -> 13.452)
BRAAM = _ev("braam", 1)                          # intro impact (v4 6.78)
SHOT_SFX = _ev("shot_sfx", 1)                    # gunshot noise burst start (v4 43.24, 0.24 s long)
STEM_END, REG_END = BRAAM + 0.02, BRAAM + 0.22   # stem silent after, mix touched only before (v4: 6.80 / 7.00)
STEM_LEN = REG_END
rng = np.random.default_rng(64)

def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()

def bp(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"); return signal.sosfilt(sos, x, axis=0)

def db(x): return 10 ** (x / 20)

song = decode(os.path.join(ROOT, ARGS.song))
mono = song.mean(1)
N = int(STEM_LEN * SR); t = np.arange(N) / SR
stem = np.zeros((N, 2))

# ---------------- 1. freeze: reversed reverb tail of the gunshot burst ----------------
b0, b1 = int(SHOT_SFX * SR), int((SHOT_SFX + 0.24) * SR)
burst = mono[b0:b1] * signal.windows.tukey(b1 - b0, 0.2)
burst = bp(burst, 1500, 12000)
L = int(2.4 * SR); tt = np.arange(L) / SR
ir = np.stack([rng.standard_normal(L), rng.standard_normal(L)], 1) * np.exp(-tt / 0.55)[:, None]
ir = signal.sosfilt(signal.butter(2, 6000, "low", fs=SR, output="sos"), ir, axis=0)
wet = np.stack([signal.fftconvolve(burst, ir[:, c]) for c in range(2)], 1)
wet = wet[int(0.05 * SR):]                        # tail only (drop the dry attack)
def comb(x, f0, g=0.93):  # E2 / E3 / B3 comb resonance -> faint tone in the key of the song
    d = int(round(SR / f0)); a = np.zeros(d + 1); a[0] = 1; a[d] = -g
    return signal.lfilter([1 - g], a, x, axis=0)
wet = 0.6 * wet + 0.4 * (comb(wet, 82.41) + comb(wet, 164.81) + 0.7 * comb(wet, 246.94)) / 2.7
rev = wet[::-1]
nf = int(T_FREEZE_END * SR)
seg = rev[-nf:] if len(rev) >= nf else np.pad(rev, ((nf - len(rev), 0), (0, 0)))
env = np.linspace(0, 1, nf) ** 1.5
env[:int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR))
seg = seg * env[:, None]
seg[-int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))[:, None]   # cut into the rewind on the jerk
seg /= np.abs(seg).max()
stem[:nf] += seg * db(-26)

# ---------------- 2. chatter: granular reverse scrub of the song ----------------
s0, s1 = int(T_FREEZE_END * SR), int(T_STOP * SR)
G = int(0.046 * SR); H = int(0.019 * SR)
chat = np.zeros((s1 - s0 + G, 2)); win = signal.windows.hann(G)
for o in range(0, s1 - s0, H):
    u = o / (s1 - s0)
    pos = SRC_FROM + (SRC_TO - SRC_FROM) * u                     # playhead in song seconds (moving backwards)
    q = 2.5 * (9 / 2.5) ** (u ** 0.8) * (1 + 0.04 * rng.standard_normal())   # pitch factor rises
    n_src = int(G * q)
    a = int(pos * SR) - n_src
    if a < 0: continue
    chunk = song[a:a + n_src][::-1]                                # reversed
    g = signal.resample_poly(chunk, G, n_src, axis=0)[:G]           # anti-aliased speed-up
    if len(g) < G: g = np.pad(g, ((0, G - len(g)), (0, 0)))
    pan = 0.5 + 0.25 * rng.uniform(-1, 1)
    g = g * np.array([1 - pan, pan]) * 2 * (0.8 + 0.4 * rng.random())
    chat[o:o + G] += g * win[:, None]
chat = chat[:s1 - s0]
chat = bp(chat, 350, 7000)
chat = signal.sosfilt(signal.butter(2, 1200, "high", fs=SR, output="sos"), chat, axis=0) * 0.6 + chat * 0.4  # thin, tape-head
u = np.linspace(0, 1, s1 - s0)
ramp = (u ** 1.6) * 0.85 + 0.15 * np.minimum(1, u / 0.08)
chat = chat / (np.sqrt((chat ** 2).mean()) + 1e-9) * ramp[:, None]

# ---------------- 3. whir: tape transport ----------------
if EL_WHIR:
    w = decode(os.path.join(OUT, "gen/rw_b.mp3"))[int(0.25 * SR):int(4.85 * SR)]
    w = signal.resample_poly(w, s1 - s0, len(w), axis=0)[:s1 - s0]
    w = bp(w, 60, 9000)
    w = w / (np.sqrt((w ** 2).mean()) + 1e-9) * (u ** 1.2)[:, None]
else:
    f = 70 * (330 / 70) ** (u ** 1.3) * (1 + 0.012 * np.sin(2 * np.pi * 7.3 * u * 3.8))
    ph = 2 * np.pi * np.cumsum(f) / SR
    motor = sum((0.6 ** k) * np.sin(k * ph + k) for k in range(1, 7))
    motor *= 1 + 0.25 * np.sin(ph / 4)                              # reel eccentricity
    hiss = bp(rng.standard_normal((s1 - s0, 2)), 3500, 12000) * (u ** 2)[:, None] * 0.8
    w = motor[:, None] * np.array([1, 1]) / 1.5 * (0.25 + 0.75 * u ** 1.2)[:, None] + hiss
    w = w / (np.sqrt((w ** 2).mean()) + 1e-9) * (0.3 + 0.7 * u)[:, None]
rew = chat * db(-29) + w * db(-36 if not EL_WHIR else -35)
rew[:int(0.006 * SR)] *= np.linspace(0, 1, int(0.006 * SR))[:, None]
rew[-int(0.003 * SR):] *= np.linspace(1, 0, int(0.003 * SR))[:, None]   # abrupt stop
stem[s0:s1] += rew
# transport clunk on the stop: short low thump + click
k = int(0.09 * SR); kt = np.arange(k) / SR
clunk = (np.sin(2 * np.pi * 95 * kt) * np.exp(-kt / 0.018) + 0.3 * bp(rng.standard_normal(k), 2000, 6000) * np.exp(-kt / 0.004))
stem[s1:s1 + k] += clunk[:, None] * db(-34)

# ---------------- kalimba protection: spectral side-chain against the song ----------------
nper = 2048
_, _, So = signal.stft(song[:N].T, SR, nperseg=nper, noverlap=nper * 3 // 4)
fr = np.fft.rfftfreq(nper, 1 / SR)
lf = np.log2(np.maximum(fr, 1))                                     # protection weight: 1 in 220-3000 Hz (kalimba fundamentals
band = np.clip(np.minimum((lf - np.log2(130)) / np.log2(220 / 130),  # + overtones), log-ramped to 0 at 130 Hz and 6.5 kHz
                          (np.log2(6500) - lf) / np.log2(6500 / 3000)), 0, 1)[None, :, None]
mo = np.abs(So).mean(0, keepdims=True)
from scipy.ndimage import minimum_filter1d
for _it in range(3):                                                  # iterate: istft overlap re-adds a little energy
    _, _, Ss = signal.stft(stem.T, SR, nperseg=nper, noverlap=nper * 3 // 4)
    ms = np.abs(Ss).mean(0, keepdims=True) + 1e-12
    gain = np.clip(mo * db(-MARGIN) / ms, db(-40), 1)
    gain = minimum_filter1d(gain, 3, axis=-1)                         # never let a neighbouring frame open it up
    gain = 1 - band * (1 - gain)
    _, sd = signal.istft(Ss * gain, SR, nperseg=nper, noverlap=nper * 3 // 4)
    stem = sd.T[:N]
stem = signal.sosfilt(signal.butter(2, 40, "high", fs=SR, output="sos"), stem, axis=0)
# keep the hard stop hard (istft smears a few ms) and silence after the clunk
stem[s1 + k:] = 0
# fades: gentle in from 0, nothing after 6.8
stem[int(STEM_END * SR):] = 0

# ---------------- mix: original + stem, only 0-7.0 s; -1 dBTP limiter on that region ----------------
REG = int(REG_END * SR)
mix = song.copy()
reg = song[:REG].astype(np.float64) + stem[:REG]
def true_peak(x): return np.abs(signal.resample_poly(x, 4, 1, axis=0)).max()
ceil = db(-1.0)
tp = true_peak(reg)
if tp > ceil:  # simple look-ahead gain limiter (only ever reduces in 0-6.8 s, unity at the 6.8-7.0 seam)
    pk = np.abs(signal.resample_poly(reg, 4, 1, axis=0)).max(1).reshape(-1, 4).max(1)
    g = np.minimum(1, ceil / np.maximum(pk, 1e-9))
    from scipy.ndimage import minimum_filter1d; g = minimum_filter1d(g, int(0.005 * SR))
    g = signal.filtfilt(np.ones(240) / 240, [1], g); g[int(STEM_END * SR):] = 1
    reg = reg * g[:, None]
mix[:REG] = reg.astype(np.float32)

sf.write(os.path.join(OUT, f"intro_sfx{TAG}.wav"), stem.astype(np.float32), SR, subtype="FLOAT")
if not ARGS.stem_only:
    sf.write(os.path.join(OUT, f"Rewind{ARGS.tag or ''}_with_intro_sfx{'_elwhir' if EL_WHIR else ''}.wav"), mix, SR, subtype="FLOAT")

# ---------------- stats ----------------
def rms_db(x): return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
st = {"true_peak_region_dBTP": 20 * np.log10(true_peak(mix[:REG].astype(np.float64))),
      "stem_peak_dBFS": 20 * np.log10(np.abs(stem).max()),
      "seg_rms_dB": {f"{a}-{b}": {"song": rms_db(song[int(a*SR):int(b*SR)]), "stem": rms_db(stem[int(a*SR):int(b*SR)])}
                     for a, b in [(0, T_FREEZE_END), (T_FREEZE_END, 2), (2, T_STOP), (T_STOP, STEM_END)]}}
# masking check in the kalimba band: song-to-stem ratio per STFT frame, 220-3000 Hz
_, _, S2 = signal.stft(stem.T, SR, nperseg=nper, noverlap=nper * 3 // 4)
bm = (fr > 220) & (fr < 3000)
eo = (np.abs(So[:, bm]) ** 2).sum((0, 1)); es = (np.abs(S2[:, bm]) ** 2).sum((0, 1)) + 1e-20
act = es > es.max() * 1e-4
st["kalimba_band_song_over_stem_dB_min_median"] = [float(np.min(10 * np.log10(eo[act] / es[act]))), float(np.median(10 * np.log10(eo[act] / es[act])))]
print(json.dumps(st, indent=1, default=float))
