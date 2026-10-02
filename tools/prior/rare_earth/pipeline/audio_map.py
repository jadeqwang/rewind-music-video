"""Build render/data/audio.json: the timing + feature map the JS renderer is driven by."""
import json
import numpy as np
import librosa

FPS = 24
SONG = "/tmp/work/song.wav"; VOC = "/tmp/work/vocals.wav"; INST = "/tmp/work/inst.wav"
OUT = "/home/user/rare-earth-techno-remix/render/data/audio.json"

y, sr = librosa.load(SONG, sr=22050, mono=True)
dur = len(y) / sr
inst, _ = librosa.load(INST, sr=22050, mono=True)
voc, _ = librosa.load(VOC, sr=22050, mono=True)

# --- beat grid (accelerando): degree-4 fit of tracked beats on the instrumental
hop = 256
oenv = librosa.onset.onset_strength(y=inst, sr=sr, hop_length=hop)
_, bt = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=hop, units="time", start_bpm=132, tightness=300)
idx = np.arange(len(bt))
c = np.polyfit(idx, bt, 4)
r = bt - np.polyval(c, idx)
keep = np.abs(r) < 0.03
c = np.polyfit(idx[keep], bt[keep], 4)
ks = np.arange(-12, len(bt) + 12)
grid = np.polyval(c, ks)
sel = (grid > -0.2) & (grid < dur)
grid, ks = grid[sel], ks[sel]
drop1 = 54.76
k_drop = ks[np.argmin(np.abs(grid - drop1))]
beats = [{"t": round(float(t), 4), "i": int(k - k_drop), "down": int((k - k_drop) % 4 == 0)} for t, k in zip(grid, ks)]
bars = [b["t"] for b in beats if b["down"]]

# --- kick / snare-ish onsets from the instrumental
S = np.abs(librosa.stft(inst, n_fft=2048, hop_length=128))
f = librosa.fft_frequencies(sr=sr, n_fft=2048)
tt = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=128)
def band_onsets(lo, hi, thr, gap):
    e = S[(f >= lo) & (f < hi)].sum(axis=0)
    d = np.maximum(0, np.diff(e, prepend=e[0]))
    d = d / (np.percentile(d, 99.5) + 1e-9)
    out = []
    for i in range(1, len(d) - 1):
        if d[i] > thr and d[i] >= d[i - 1] and d[i] >= d[i + 1]:
            if not out or tt[i] - out[-1][0] > gap:
                out.append((float(tt[i]), float(min(1.5, d[i]))))
    return out
kicks = band_onsets(35, 110, 0.35, 0.25)
snares = band_onsets(1800, 5000, 0.45, 0.2)

# --- per-frame features at FPS
nfr = int(np.ceil(dur * FPS))
ft = np.arange(nfr) / FPS
def env(sig, lo=None, hi=None):
    Sx = np.abs(librosa.stft(sig, n_fft=2048, hop_length=256))
    fx = librosa.fft_frequencies(sr=sr, n_fft=2048)
    if lo is not None:
        Sx = Sx[(fx >= lo) & (fx < hi)]
    e = np.sqrt((Sx ** 2).sum(axis=0))
    te = librosa.frames_to_time(np.arange(len(e)), sr=sr, hop_length=256)
    v = np.interp(ft, te, e)
    return v / (np.percentile(v, 99) + 1e-9)
feat = {
    "energy": env(y), "low": env(inst, 30, 150), "mid": env(inst, 150, 2500),
    "high": env(inst, 5000, 11000), "vocal": env(voc, 150, 5000),
}
feat = {k: [round(float(min(1.5, x)), 3) for x in v] for k, v in feat.items()}

# --- lyrics
words = json.load(open("/tmp/work/lyrics_words_v3.json"))
lines = []
for li in sorted(set(w["line"] for w in words)):
    ws = [w for w in words if w["line"] == li]
    lines.append({"i": li, "sec": ws[0]["sec"], "t": ws[0]["t"], "end": ws[-1]["end"],
                  "text": " ".join(w["word"] for w in ws),
                  "words": [{"w": w["word"], "t": w["t"], "end": w["end"]} for w in ws]})

sections = [
    {"id": "open", "t": 0.0, "end": 3.1, "label": "cold open"},
    {"id": "v1", "t": 3.1, "end": 17.9, "label": "verse 1 (earth, asking)"},
    {"id": "v2", "t": 17.9, "end": 39.95, "label": "verse 2 (earth, the signal)"},
    {"id": "build", "t": 39.95, "end": 54.4, "label": "build (the other world)"},
    {"id": "v3", "t": 54.4, "end": 75.3, "label": "drop 1 / verse 3 (the filter, keep looking)"},
    {"id": "v4", "t": 75.3, "end": 89.9, "label": "drop 2a / verse 4 (call and response)"},
    {"id": "v5", "t": 89.9, "end": 111.9, "label": "drop 2b / verse 5 (arrival)"},
    {"id": "final", "t": 111.9, "end": 123.4, "label": "final drop (contact)"},
    {"id": "outro", "t": 123.4, "end": round(dur, 3), "label": "outro"},
]
json.dump({"duration": round(dur, 3), "fps": FPS, "bpm_start": round(60 / (beats[5]["t"] - beats[4]["t"]), 2),
           "beats": beats, "bars": [round(b, 4) for b in bars], "kicks": [[round(a, 4), round(b, 3)] for a, b in kicks],
           "snares": [[round(a, 4), round(b, 3)] for a, b in snares], "sections": sections, "lines": lines,
           "features": feat}, open(OUT, "w"))
print("beats", len(beats), "bars", len(bars), "kicks", len(kicks), "snares", len(snares), "frames", nfr)
print("bars near sections:", [(s["id"], min(bars, key=lambda b: abs(b - s["t"]))) for s in sections])
