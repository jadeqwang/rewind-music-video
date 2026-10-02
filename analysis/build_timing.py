"""Build analysis/timing.json + envelopes.json for "Rewind (4).mp3".

Inputs (produced earlier in this folder):
  stems/vocals.wav, stems/no_vocals.wav   (separate_mdx.py, UVR MDX-Net Kim_Vocal_2)
  mm_db_mix.npy                           (madmom RNN+DBN downbeat tracker on the full mix, madmom_db.py)
  whisper_turbo_vocals.json               (Cloudflare @cf/openai/whisper-large-v3-turbo on the vocal stem)
Hand-verified constants (tape stops, silences, inhales, shot SFX) are documented inline; they were
read off fine-grained (10 ms) band-energy / spectral-centroid / flatness traces (see TIMING_NOTES.md).
"""
import json, re, difflib, os
import numpy as np, librosa, soundfile as sf, scipy.signal as ss

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
SONG = P('..', 'Rewind (4).mp3')
SR = 48000

y2, _ = librosa.load(SONG, sr=SR, mono=False)
y = y2.mean(0)
DUR = len(y) / SR
voc = sf.read(P('stems', 'vocals.wav'))[0].mean(1)
inst = sf.read(P('stems', 'no_vocals.wav'))[0].mean(1)

# ------------------------------------------------------------------ beats / bars
mm = np.load(P('mm_db_mix.npy'))
bt_raw, pos = mm[:, 0].copy(), mm[:, 1].astype(int)
# de-quantise madmom's 10 ms grid with a local linear fit (+-4 beats); keep raw where it deviates (>15 ms)
bt = bt_raw.copy()
for i in range(len(bt)):
    lo, hi = max(0, i - 4), min(len(bt), i + 5)
    k = np.arange(lo, hi)
    c = np.polyfit(k, bt_raw[lo:hi], 1)
    f = np.polyval(c, i)
    if abs(f - bt_raw[i]) < 0.015:
        bt[i] = f
bt = np.round(bt, 4)
down_idx = np.where(pos == 1)[0]
downbeats = bt[down_idx]
bar_of_beat = np.cumsum(pos == 1)  # bar number (1-based) for each beat
GRID_END = 227.20  # last musical hit; after this only the decaying tail (madmom keeps ticking)


def bar_t(n):  # start time of bar n (1-based)
    return float(downbeats[n - 1])


ibi = np.diff(bt)
bpm_global = 60 / np.median(ibi[(bt[:-1] > 45) & (bt[:-1] < 215)])

# ------------------------------------------------------------------ sections
S = []
def sec(name, a, b, note=''):
    S.append(dict(name=name, start=round(a, 3), end=round(b, 3), note=note))

# hand-verified gap constants (seconds)
TS1, SIL1, DROP1_ON = 43.42, 43.92, 45.12    # tape-stop pitch/centroid dive 43.44->43.92, inst. silent to 45.08
TS2, SIL2, DROP2_ON = 102.84, 103.28, 104.45  # dive 102.84->103.28, inst. silent to ~104.40
CUT3, SIL3_FULL, DROP3_ON = 170.62, 171.28, 171.50  # hard cut (no tape stop); vocal "stop" rings to 171.26
BRK_CUT = 149.12                              # everything drops out -> near-silence to 151.2
END_HIT = 227.20

sec('intro', 0.0, bar_t(8), 'ambient: rain/insects, kalimba, drone; faint ~126 BPM tick pulse (not truly unmetered); low impact at 6.78; breathy vocal pickup from ~12.3')
sec('verse1', bar_t(8), bar_t(16), 'whispered verse, sparse percussion, sub hits every other bar')
sec('build1', bar_t(16), TS1, 'cello ostinato / timpani / riser; accelerating figures in last 2 bars')
sec('tapestop1', TS1, SIL1, 'instrumental pitch-dive (tape stop) right after "shot"')
sec('silence1', SIL1, DROP1_ON, 'instrument silent; only vocal: inhale 43.73, "and time stops"')
sec('drop1', bar_t(25), bar_t(39), 'braam + 4-on-floor kick + distorted sub; "Rewind. Rewind." then pitched vocal chops ("hoots")')
sec('verse3', bar_t(39), bar_t(49), 'pulsing sub, toms; vocal enters on bar 39, texture thins at bar 41 (74.94)')
sec('build2', bar_t(49), TS2, 'taiko/timpani, Shepard riser, choir; "I zigzag..."')
sec('tapestop2', TS2, SIL2, 'tape-stop dive after second "shot"')
sec('silence2', SIL2, DROP2_ON, 'instrument silent; inhale 103.11, "and time stops"')
sec('drop2', bar_t(57), bar_t(73), 'darker/heavier drop; "Rewind." x2 (112.6, 116.4), stuttering chops')
sec('breakdown', bar_t(73), bar_t(89), 'kalimba + low drone; low-brass hits on alternate bars (137.4/141.6/145.4); whispered verse-1 reprise from 147.4; full drop-out 149.1-151.2')
sec('build3', bar_t(89), CUT3, 'horror build, heartbeat kick, sustained choir; "Never stop."')
sec('silence3', CUT3, DROP3_ON, 'hard cut (no tape stop): vocal "stop" alone 170.62-171.26, then true digital silence 171.28-171.50')
sec('final_drop', bar_t(93), bar_t(117), 'darkest/heaviest, 4-on-floor, chopped "I dreamt" vocal')
sec('instrumental', bar_t(117), END_HIT, 'stripped outro: sub/braam on alternate bars (219.60, 223.40), pitched-down hoots')
sec('end', END_HIT, DUR, 'abrupt end: final low hit 227.20, sustained ~2 s, fades to near-silence by ~231.5')

# ------------------------------------------------------------------ helpers: frame envelopes
def env_db(x, hop, win):
    e = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, 'same')[::hop] + 1e-12)
    return 20 * np.log10(e)

VH = 480  # 10 ms
vdb = env_db(voc, VH, 960)
vt = np.arange(len(vdb)) * VH / SR
VACT = -45.0  # vocal-stem activity threshold (dBFS)
vact = vdb > VACT

# ------------------------------------------------------------------ lyrics + whisper alignment
LYR = [
    "The night before my dissertation defense,",
    "I'm speeding down Lake Shore, I dreamt",
    "a shadow chasing me I couldn't place",
    "I pulled over, and men in shades and suits,",
    "I reach for my ID to show … and I do,",
    "With no warning I get shot … and time stops",
    "Rewind.",
    "Rewind.",
    "And now I'm back on the road",
    "sirens in my mirror …Reload.",
    "A shadow chasing me like it's a race",
    "I zigzag across the field of grass",
    "they chase me and they're just too fast",
    "With no warning I get shot … and time stops",
    "Rewind.",
    "Rewind.",  # sung a 2nd time (lyrics sheet has one)
    "The night before my dissertation defense,",
    "I'm speeding down Lake Shore, I dreamt",
    "a shadow chasing me I couldn't place",
    "Never stop.",
]
norm = lambda w: re.sub(r"[^a-z']", '', w.lower().replace('’', "'"))
lw = []  # (display word, norm, line_idx)
for li, line in enumerate(LYR):
    for w in line.replace('…', ' ').split():
        if norm(w):
            lw.append((w.strip(',.'), norm(w), li))

wj = json.load(open(P('whisper_turbo_vocals.json')))['result']
ww = [(w['word'].strip(), norm(w['word']), w['start'], w['end']) for s in wj['segments'] for w in s['words']]
# drop whisper hallucinated/chop tokens after "Never stop" and the "Boys" hoots / "Stop, stop" echoes (handled as events)
CHOP_TOKENS = []
keep = []
for i, w in enumerate(ww):
    t = w[2]
    if (w[1] == 'boys') or (w[1] in ('dreamt', 'i', 'amen') and t > 171.2) or (w[1] in ('stop',) and 44.9 < t < 47):
        CHOP_TOKENS.append(w)
    else:
        keep.append(w)
ww = keep

sm = difflib.SequenceMatcher(a=[x[1] for x in lw], b=[x[1] for x in ww], autojunk=False)
times = [None] * len(lw)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal':
        for k in range(i2 - i1):
            times[i1 + k] = [ww[j1 + k][2], ww[j1 + k][3]]
    elif tag == 'replace' or (tag == 'insert'):
        if i2 > i1 and j2 > j1:
            a, b = ww[j1][2], ww[j2 - 1][3]
            L = np.array([len(lw[k][1]) + 1 for k in range(i1, i2)], float)
            cs = np.r_[0, np.cumsum(L)] / L.sum()
            for n, k in enumerate(range(i1, i2)):
                times[k] = [a + (b - a) * cs[n], a + (b - a) * cs[n + 1]]
# interpolate any unmatched (delete) words between neighbours
for k in range(len(lw)):
    if times[k] is None:
        p = next(times[j][1] for j in range(k - 1, -1, -1) if times[j])
        q = next((times[j][0] for j in range(k + 1, len(lw)) if times[j]), p + 0.4)
        times[k] = [p, min(q, p + 0.4)]

# hand-verified overrides (vocal-stem flatness/energy traces): the tape-stop tails whisper mis-heard
OVR = {
    # loop 1: "shot" 'sh' 42.89, inhale 43.73-43.85, "and" 43.85, "time" 44.15, "stops" 's' 44.88 (drop lands on "-tops")
    (5, 'shot'): (42.89, 43.38), (5, 'and'): (43.85, 44.13), (5, 'time'): (44.15, 44.86), (5, 'stops'): (44.88, 45.42),
    # loop 2: "shot" 102.28, inhale 103.11-103.20, "and" 103.21, "time" 103.51, "stops" 104.25 (drop 104.50 on "-tops")
    (13, 'shot'): (102.28, 102.82), (13, 'and'): (103.21, 103.46), (13, 'time'): (103.51, 104.22), (13, 'stops'): (104.25, 104.80),
    # verse-1 opener: breathy pickup from ~12.3, first syllable onset 13.55, "night" 14.20
    (0, 'the'): (13.55, 14.20),
    # verse 3: 71.2-72.3 is a vocal chop; phrase onset after a gap at 73.55
    (8, 'and'): (73.55, 73.76), (8, 'now'): (73.77, 74.34),
    # "Never" hides under the build3 choir (onset 169.77); "stop" is exposed in the hard cut 170.62-171.26
    (19, 'never'): (169.77, 170.60), (19, 'stop'): (170.62, 171.26),
}
for k, (w, n, li) in enumerate(lw):
    if (li, n) in OVR:
        times[k] = list(OVR[(li, n)])


def refine(s, e, nxt):
    """whisper word END times are reliable, STARTS are padded back to the previous word end.
    Snap edges to vocal-stem activity: trailing silence trims the end, internal silences
    (>=120 ms) move the start to the last voiced run, a silent start moves to the first voiced frame."""
    i0, i1 = int(round(s * 100)), int(round(e * 100))
    i1 = max(i1, i0 + 2)
    seg = vact[i0:i1]
    # runs of inactivity
    d = np.diff(np.r_[1, seg.astype(int), 1])
    rs, re_ = np.where(d == -1)[0], np.where(d == 1)[0]
    runs = [(a, b) for a, b in zip(rs, re_) if b - a >= 12]
    if runs and runs[-1][1] >= len(seg) - 1 and runs[-1][0] > 8:  # trailing silence
        i1 = i0 + runs[-1][0]
        runs = runs[:-1]
    if runs and runs[-1][1] < (i1 - i0) - 6:
        i0 = i0 + runs[-1][1]
    elif not vact[i0]:
        w = np.where(vact[i0:i1])[0]
        if len(w):
            i0 = min(i0 + w[0], i1 - 6)
    s2, e2 = i0 / 100, i1 / 100
    if nxt is not None:
        e2 = min(e2, nxt)
    return round(s2, 3), round(max(e2, s2 + 0.06), 3)

words = []
for k, (w, n, li) in enumerate(lw):
    s, e = times[k]
    nxt = times[k + 1][0] if k + 1 < len(lw) else None
    if (li, n) in OVR:
        s2, e2 = OVR[(li, n)]
    else:
        s2, e2 = refine(s, e, nxt)
    words.append(dict(w=w, start=s2, end=e2, line_idx=li))
# enforce monotonic
for k in range(1, len(words)):
    if words[k]['start'] < words[k - 1]['start']:
        words[k]['start'] = words[k - 1]['end']
    if words[k - 1]['end'] > words[k]['start']:
        words[k - 1]['end'] = words[k]['start']

lines = []
for li, text in enumerate(LYR):
    ws = [w for w in words if w['line_idx'] == li]
    lines.append(dict(text=text, start=ws[0]['start'], end=ws[-1]['end']))

# per-word vocal-stem check
for w in words:
    a, b = int(w['start'] * 100), int(w['end'] * 100)
    w['voc_db'] = round(float(np.max(vdb[a:max(b, a + 1)])), 1)

# ------------------------------------------------------------------ events
ev = []
def E(type_, t, **kw):
    ev.append(dict(type=type_, t=round(float(t), 3), **kw))

E('braam', 6.78, note='intro low impact (sub + broadband swell), beat 3 of bar 4')
E('shot', 42.89, note='loop 1: vocal "shot" (sh-onset)')
E('shot_sfx', 43.24, note='loop 1: noise-burst/whip hit in instrumental (centroid >4 kHz) 43.24-43.48')
E('tapestop', TS1, end=SIL1, note='loop 1 tape-stop dive')
E('inhale', 43.73, end=43.85, note='sharp inhale (vocal stem, noisy/flat spectrum)')
E('silence', SIL1, end=DROP1_ON, note='instrumental silence; vocal "and time stops" over it')
E('drop', bar_t(25), note='DROP 1 downbeat (bar 25) - braam + kick + sub; lands on "(s)tops"')
E('braam', bar_t(25), note='drop 1 braam')
E('shot', 102.28, note='loop 2: vocal "shot"')
E('shot_sfx', 102.56, note='loop 2: noise-burst hit 102.56-102.84')
E('tapestop', TS2, end=SIL2, note='loop 2 tape-stop dive')
E('inhale', 103.11, end=103.20, note='sharp inhale')
E('silence', SIL2, end=DROP2_ON, note='instrumental silence; "and time stops"')
E('drop', bar_t(57), note='DROP 2 downbeat (bar 57)')
E('braam', bar_t(57), note='drop 2 braam')
for t in (137.41, 141.60, 145.38):
    E('braam', t, note='breakdown low-brass/sub hit (alternate bars)')
E('silence', BRK_CUT, end=151.20, note='breakdown full drop-out ("The night before" ... "my dissertation")')
E('silence', CUT3, end=DROP3_ON, note='pre-final-drop hard cut; "stop" alone then digital silence 171.28-171.50')
E('drop', bar_t(93), note='FINAL DROP downbeat (bar 93)')
E('braam', bar_t(93), note='final drop braam')
E('section', bar_t(117), note='final drop -> stripped instrumental')
for t in (219.60, 223.40):
    E('braam', t, note='instrumental sub/braam hit')
E('end', END_HIT, note='last hit - groove stops abruptly; tail decays to ~231.5')

# vocal-chop / ad-lib regions = vocal activity not covered by lyric words
covered = np.zeros_like(vact)
for w in words:
    covered[int(w['start'] * 100) - 5:int(w['end'] * 100) + 5] = True
act = vact & ~covered
act = ss.medfilt(act.astype(float), 15) > 0.5
d = np.diff(np.r_[0, act.astype(int), 0])
on, off = np.where(d == 1)[0], np.where(d == -1)[0]
chops = []
for a, b in zip(on, off):
    if b - a >= 15:
        chops.append(dict(start=a / 100, end=b / 100, peak_db=round(float(vdb[a:b].max()), 1)))
# merge gaps < 0.12 s
mc = []
for c in chops:
    if mc and c['start'] - mc[-1]['end'] < 0.12:
        mc[-1]['end'] = c['end']; mc[-1]['peak_db'] = max(mc[-1]['peak_db'], c['peak_db'])
    else:
        mc.append(c)
# label with whisper's guess where available
for c in mc:
    lab = [w[0] for w in CHOP_TOKENS if c['start'] - 0.3 <= w[2] <= c['end']]
    c['heard'] = ' '.join(lab)

# kicks in drops: beats inside drop sections, refined to sub-band (30-90 Hz) onset within +-40 ms
sos = ss.butter(4, [30, 90], 'band', fs=SR, output='sos')
sub = ss.sosfiltfilt(sos, y)
sdb = env_db(sub, 48, 96)  # 1 ms
sfl = np.maximum(0, np.diff(sdb, prepend=sdb[0]))
kicks = []
for s_ in S:
    if s_['name'] in ('drop1', 'drop2', 'final_drop', 'verse3', 'build2'):
        for t in bt[(bt >= s_['start'] - 0.01) & (bt < s_['end'] - 0.01)]:
            i = int(t * 1000)
            w = sfl[i - 40:i + 40]
            j = i - 40 + int(np.argmax(np.convolve(w, np.ones(5), 'same')))
            kicks.append(round(j / 1000, 3))

# ------------------------------------------------------------------ envelopes @30fps
FPS = 30
NF = int(np.ceil(DUR * FPS))
hop = SR // FPS  # 1600
nfft = 4096
pad = nfft // 2
yp = np.pad(y, (pad, pad + nfft))
Sx = np.abs(librosa.stft(y, n_fft=nfft, hop_length=hop, center=True))[:, :NF]
fr = librosa.fft_frequencies(sr=SR, n_fft=nfft)
def band(lo, hi):
    return 10 * np.log10((Sx[(fr >= lo) & (fr < hi)] ** 2).sum(0) + 1e-10)
def frame_rms(x):
    r = librosa.feature.rms(y=x, frame_length=3200, hop_length=hop, center=True)[0][:NF]
    return 20 * np.log10(r + 1e-7)
def nz(xdb, floor_pct=1, top_pct=99.7, floor_abs=None):
    lo = np.percentile(xdb, floor_pct) if floor_abs is None else floor_abs
    hi = np.percentile(xdb, top_pct)
    return np.clip((xdb - lo) / (hi - lo), 0, 1)
env = {}
env['rms'] = nz(frame_rms(y), floor_abs=-60)
env['low'] = nz(band(20, 150), 5)
env['mid'] = nz(band(150, 2000), 5)
env['high'] = nz(band(2000, 16000), 5)
vr = frame_rms(voc)
env['vocal'] = nz(vr, floor_abs=-50)
env['inst'] = nz(frame_rms(inst), floor_abs=-60)
# onset strength (mel spectral flux) at 4 ms resolution, max-pooled into 30 fps frames
oh = 192
oe = librosa.onset.onset_strength(y=y, sr=SR, hop_length=oh, n_mels=128)
ot = np.arange(len(oe)) * oh / SR
of = np.zeros(NF)
idx = np.minimum((ot * FPS + 0.5).astype(int), NF - 1)
np.maximum.at(of, idx, oe)
env['onset'] = np.clip(of / np.percentile(of, 99.7), 0, 1)
# spectral flux hit list (peak-picked, with dominant band)
pk, pr = ss.find_peaks(oe, distance=int(0.09 * SR / oh), prominence=np.percentile(oe, 95))
Sm = np.abs(librosa.stft(y, n_fft=2048, hop_length=oh))
fm = librosa.fft_frequencies(sr=SR, n_fft=2048)
flux = np.maximum(0, np.diff(np.log1p(Sm), axis=1, prepend=np.log1p(Sm[:, :1])))
bands_ = {'low': (fm < 150), 'mid': (fm >= 150) & (fm < 2000), 'high': fm >= 2000}
hits = []
top = np.percentile(oe[pk], 99) if len(pk) else 1
for p in pk:
    contrib = {k: float(flux[m, p].sum()) for k, m in bands_.items()}
    hits.append(dict(t=round(float(ot[p]), 3), s=round(float(min(1, oe[p] / top)), 3), band=max(contrib, key=contrib.get)))

# ------------------------------------------------------------------ bpm drift per section
sec_bpm = {}
for s_ in S:
    m = (bt[:-1] >= s_['start']) & (bt[1:] <= s_['end'])
    if m.sum() >= 4:
        sec_bpm[s_['name']] = round(float(60 / np.median(ibi[m])), 2)
    s_['bpm'] = sec_bpm.get(s_['name'])
    s_['bar_start'] = int(bar_of_beat[np.searchsorted(bt, s_['start'] - 0.02)]) if s_['start'] < bt[-1] else None
bar_bpm = [dict(bar=int(n + 1), t=float(downbeats[n]),
                bpm=round(float(240 / (downbeats[n + 1] - downbeats[n])), 2)) for n in range(len(downbeats) - 1)]

timing = dict(
    source='Rewind (4).mp3', duration=round(DUR, 3), sr=SR,
    bpm=round(float(bpm_global), 2),
    bpm_note='Song is ~130 BPM (not 124): 125.5-127 in intro/verse1, ~129 in drop1/verse3, ~130 in drop2 & final drop, ~128 in breakdown, slowing to ~126 in the outro. madmom DBN grid, 4/4; drops all land on downbeats of the continuous grid.',
    grid_end=GRID_END,
    beats=[float(x) for x in bt],
    beat_pos=[int(x) for x in pos],
    downbeats=[float(x) for x in downbeats],
    bars=[dict(bar=i + 1, t=float(t)) for i, t in enumerate(downbeats)],
    bar_bpm=bar_bpm,
    sections=S,
    lines=lines,
    words=words,
    events=sorted(ev, key=lambda e: e['t']),
    vocal_chops=mc,
    kicks=kicks,
    hits=hits,
)
json.dump(timing, open(P('timing.json'), 'w'), indent=1, ensure_ascii=False)
json.dump(dict(fps=FPS, n_frames=NF, duration=round(DUR, 3),
               desc=dict(rms='mix RMS dB, -60dB..p99.7 -> 0..1', low='20-150 Hz band energy (sub/kick)',
                         mid='150-2000 Hz', high='2-16 kHz', vocal='vocal-stem RMS, -50dB..p99.7',
                         inst='instrumental-stem RMS', onset='mel spectral-flux onset strength, max-pooled per frame'),
               frame_time='frame i is centred at t = i/30 s',
               **{k: [round(float(v), 3) for v in a] for k, a in env.items()}),
          open(P('envelopes.json'), 'w'), separators=(',', ':'))
print('beats', len(bt), 'bars', len(downbeats), 'bpm', bpm_global)
print('sections'); [print(f"  {s_['name']:12s} {s_['start']:8.3f} {s_['end']:8.3f} bar {s_['bar_start']} bpm {s_['bpm']}") for s_ in S]
print('lines'); [print(f"  {l['start']:8.3f} {l['end']:8.3f} {l['text']}") for l in lines]
print('chops', len(mc), 'kicks', len(kicks), 'hits', len(hits))
