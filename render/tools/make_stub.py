# Stub timing + envelopes for the renderer until analysis/timing.json exists.
# Words from analysis/whisper_turbo_vocals.json; beats = 124 BPM grid phase-fitted to percussive onsets;
# envelopes at 30 fps from the mix and vocal stem. Output: render/data/timing.stub.json, envelopes.stub.json
import json, numpy as np, librosa, os
R = os.path.dirname(os.path.abspath(__file__)) + '/..'
A = R + '/../analysis'
sr = 22050; fps = 30; hop = sr // fps  # 735
y, _ = librosa.load(R + '/../Rewind (4).mp3', sr=sr, mono=True)
dur = len(y) / sr
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
f = librosa.fft_frequencies(sr=sr, n_fft=2048)
def band(a, b):
    e = S[(f >= a) & (f < b)].mean(0); return e
def norm(x):
    x = np.asarray(x, float); p = np.percentile(x, 99.5) or 1; return np.clip(x / p, 0, 1)
rms = norm(librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0])
low, mid, high = norm(band(20, 160)), norm(band(160, 2000)), norm(band(2000, 11000))
onset = norm(librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop))
try:
    v, _ = librosa.load(A + '/stems/vocals.wav', sr=sr, mono=True)
    vocal = norm(librosa.feature.rms(y=v, frame_length=2048, hop_length=hop)[0])
except Exception:
    vocal = np.zeros_like(rms)
n = int(np.ceil(dur * fps))
env = {k: [round(float(x), 3) for x in np.pad(a, (0, max(0, n - len(a))))[:n]] for k, a in
       dict(rms=rms, low=low, mid=mid, high=high, vocal=vocal, onset=onset).items()}
env['fps'] = fps
json.dump(env, open(R + '/data/envelopes.stub.json', 'w'))
# beat grid: 124 bpm, phase fit on low-band onsets 45..102 s
T = 60 / 124
oe = norm(librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, fmax=200))
best = (0, 0)
for ph in np.arange(0, T, 0.002):
    ts = np.arange(45 + ph, 100, T); idx = (ts * fps).astype(int)
    s = oe[idx].mean()
    if s > best[0]: best = (s, ph)
ph = best[1] + 45
first = ph - np.floor((ph - 0.0) / T) * T
beats = [round(float(b), 4) for b in np.arange(first, dur, T)]
words, lines = [], []
W = json.load(open(A + '/whisper_turbo_vocals.json'))['result']
for li, s in enumerate(W['segments']):
    lines.append(dict(text=s['text'].strip(), start=round(s['start'], 3), end=round(s['end'], 3)))
    for w in s['words']:
        words.append(dict(w=w['word'].strip(), start=round(w['start'], 3), end=round(w['end'], 3), line_idx=li))
secs = [('intro', 0, 13), ('verse1', 13, 29.5), ('build1', 29.5, 47), ('tapestop1', 47, 49.5), ('drop1', 49.5, 71),
        ('verse3', 71, 88.9), ('build2', 88.9, 105), ('tapestop2', 105, 108), ('drop2', 108, 146), ('breakdown', 146, 165),
        ('build3', 165, 180), ('final_drop', 180, 215), ('outro', 215, dur)]
json.dump(dict(stub=True, duration=round(dur, 3), bpm=124, beats=beats, downbeats=beats[::4],
               sections=[dict(name=a, start=b, end=c) for a, b, c in secs], words=words, lines=lines,
               events=[]), open(R + '/data/timing.stub.json', 'w'), indent=0)
print('dur', dur, 'beat phase', first, 'n beats', len(beats))
for t in np.arange(40, 56, 0.25): print(f"{t:6.2f} rms {rms[int(t*fps)]:.2f} low {low[int(t*fps)]:.2f} voc {vocal[int(t*fps)]:.2f}")
