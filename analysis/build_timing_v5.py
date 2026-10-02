"""Timing check "Rewind (4).mp3" vs "Rewind (5).mp3" and v5 re-analysis.

Finding: v5 is NOT on the v4 timeline. It is v4 conformed to a constant 129.000 BPM grid (DAW-style warp), so the
offset t5 - t4 drifts smoothly between ~-480 ms and ~+80 ms. This script measures the warp and writes:
  timing_v5.json      timing.json mapped to v5 time (+ `time_map` anchors v4<->v5, recomputed hits/kicks/bpm)
  envelopes_v5.json   per-frame envelopes computed on v5 audio (same method/format as envelopes.json)
  v5_verify.json      all verification numbers (window xcorr, beats, events, lyric lines)
Inputs: ../Rewind (4).mp3, ../Rewind (5).mp3, timing.json, mm_db_mix_v5.npy (madmom_db_v5.py),
        stems_v5/{vocals,no_vocals}.wav (separate_mdx.py "../Rewind (5).mp3" stems_v5), stems/vocals.wav (v4)

Mapping function (v4 seconds -> v5 seconds): piecewise-linear interpolation through time_map.v4 / time_map.v5
(one anchor per beat, measured by 1 ms onset-envelope cross-correlation), linear extrapolation at both ends:
    t5 = np.interp(t4, tm['v4'], tm['v5'])   # inverse: np.interp(t5, tm['v5'], tm['v4'])
"""
import os, json, subprocess, numpy as np, librosa, soundfile as sf, numba, scipy.signal as ss

HERE = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(HERE, *a)
SR = 48000
V4, V5 = P('..', 'Rewind (4).mp3'), P('..', 'Rewind (5).mp3')


def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-map", "0:a", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


a2, b2 = dec(V4), dec(V5)
a, b = a2.mean(1), b2.mean(1)
T = json.load(open(P('timing.json')))
VER = {'len_v4': len(a) / SR, 'len_v5': len(b) / SR}
print('decoded length v4 %.4f  v5 %.4f' % (len(a) / SR, len(b) / SR))

# ------------------------------------------------ 1. naive (unwarped) onset-envelope xcorr at 100 Hz
H = 480
oa = librosa.onset.onset_strength(y=a, sr=SR, hop_length=H, n_mels=128)
ob = librosa.onset.onset_strength(y=b, sr=SR, hop_length=H, n_mels=128)


def zc(u, v):
    u = (u - u.mean()) / (u.std() + 1e-9); v = (v - v.mean()) / (v.std() + 1e-9); return float((u * v).mean())


def best_lag(u_ref, v_full, i0, i1, maxlag):
    """lag L (frames) maximising corr(u_ref[i0:i1], v_full[i0+L:i1+L]); parabolic sub-frame."""
    rs = np.array([zc(u_ref[i0:i1], v_full[i0 + L:i1 + L]) if 0 <= i0 + L and i1 + L <= len(v_full) else -1
                   for L in range(-maxlag, maxlag + 1)])
    k = int(np.argmax(rs)); d = 0.0
    if 0 < k < len(rs) - 1:
        den = rs[k - 1] - 2 * rs[k] + rs[k + 1]; d = 0.5 * (rs[k - 1] - rs[k + 1]) / den if den else 0
    return k - maxlag + d, float(rs[k]), float(rs[maxlag])


n = min(len(oa), len(ob))
full = ss.correlate((ob[:n] - ob[:n].mean()) / ob[:n].std(), (oa[:n] - oa[:n].mean()) / oa[:n].std(), 'full') / n
lags = np.arange(-n + 1, n); k = int(np.argmax(full))
VER['naive_global'] = dict(best_lag_ms=float(lags[k] * 10), r=float(full[k]), r_at_0=float(full[n - 1]),
                           note='v5 vs v4 onset envelope, whole track; positive lag = v5 later. No dominant peak -> no constant offset.')
VER['naive_windows_10s'] = []
for s in range(0, 230, 10):
    i0, i1 = s * 100, min((s + 10) * 100, n - 120)
    L, r, r0 = best_lag(oa, ob, i0, i1, 100)       # v5 relative to v4 (positive = v5 later)
    VER['naive_windows_10s'].append(dict(t=s, lag_ms=round(L * 10, 1), r=round(r, 3), r_at_0=round(r0, 3)))
print('naive global:', VER['naive_global'])

# ------------------------------------------------ 2. coarse warp: banded DTW on mel features @100 Hz
def mel(x): return librosa.power_to_db(librosa.feature.melspectrogram(y=x, sr=SR, n_fft=2048, hop_length=H, n_mels=64))


def feat(M):
    F = np.maximum(0, np.diff(M, axis=1, prepend=M[:, :1])); S = M - M.mean(0, keepdims=True)
    return np.vstack([S / (np.linalg.norm(S, axis=0, keepdims=True) + 1e-9),
                      1.5 * F / (np.linalg.norm(F, axis=0, keepdims=True) + 1e-3)]).astype(np.float32)


@numba.njit
def band_dtw(XA, XB, KMIN, KMAX, pen):  # path[j] = k : v5 frame j <-> v4 frame j+k
    nA = XA.shape[1]; nB = XB.shape[1]; K = KMAX - KMIN + 1
    D = np.full((nB, K), 1e18); Pm = np.zeros((nB, K), np.int8)
    for j in range(nB):
        for kk in range(K):
            i = j + kk + KMIN
            if i < 0 or i >= nA:
                c = 2.0
            else:
                s = 0.0; na = 0.0; nb = 0.0
                for f in range(XA.shape[0]):
                    s += XA[f, i] * XB[f, j]; na += XA[f, i] ** 2; nb += XB[f, j] ** 2
                c = 1 - s / np.sqrt(na * nb + 1e-12)
            if j == 0:
                D[j, kk] = c; continue
            best = D[j - 1, kk]; p = 0
            if kk > 0 and D[j, kk - 1] + pen < best: best = D[j, kk - 1] + pen; p = 1
            if kk < K - 1 and D[j - 1, kk + 1] + pen < best: best = D[j - 1, kk + 1] + pen; p = 2
            D[j, kk] = best + c; Pm[j, kk] = p
    kk = np.argmin(D[nB - 1]); j = nB - 1; path = np.zeros(nB, np.int64); path[j] = kk + KMIN
    while j > 0:
        p = Pm[j, kk]
        if p == 0: j -= 1
        elif p == 1: kk -= 1
        else: j -= 1; kk += 1
        path[j] = kk + KMIN
    return path


dl = band_dtw(feat(mel(a)), feat(mel(b)), -100, 100, 0.3)
t5g = np.arange(len(dl)) / 100; t4g = t5g + dl / 100
t4g = np.maximum.accumulate(t4g)
coarse = lambda t4: np.interp(t4, t4g, t5g)

# ------------------------------------------------ 3. fine anchors: one per v4 beat, 1 ms onset envelope xcorr
H2 = 48
pa = librosa.onset.onset_strength(y=a, sr=SR, hop_length=H2, n_mels=64)
pb = librosa.onset.onset_strength(y=b, sr=SR, hop_length=H2, n_mels=64)


def fine_at(t4, W=250, ML=60, x4=pa, x5=pb, pred=None):
    """measured v5 time of the audio at v4 time t4 (window +-W ms, search +-ML ms around the coarse prediction)."""
    i = int(round(t4 * 1000)); j0 = int(round((coarse(t4) if pred is None else pred) * 1000))
    if i - W < 0 or i + W > len(x4): return np.nan, 0.0
    u = x4[i - W:i + W]; rs = []
    for L in range(-ML, ML + 1):
        j = j0 + L
        rs.append(zc(u, x5[j - W:j + W]) if j - W >= 0 and j + W <= len(x5) else -1)
    rs = np.array(rs); k = int(np.argmax(rs)); d = 0.0
    if 0 < k < len(rs) - 1:
        den = rs[k - 1] - 2 * rs[k] + rs[k + 1]; d = 0.5 * (rs[k - 1] - rs[k + 1]) / den if den else 0
    return (j0 + k - ML + d) / 1000, float(rs[k])


b4 = np.array(T['beats'])
anc = np.array([fine_at(t) for t in b4])
off = anc[:, 0] - b4
good = (anc[:, 1] > 0.4) & np.isfinite(off)
med = ss.medfilt(np.where(good, off, np.interp(b4, b4[good], off[good])), 7)
good &= np.abs(off - med) < 0.015
A4, A5 = b4[good], anc[good, 0]
assert np.all(np.diff(A5) > 0)
s0 = (A5[1] - A5[0]) / (A4[1] - A4[0]); s1 = (A5[-1] - A5[-2]) / (A4[-1] - A4[-2])


def m45(t):  # v4 -> v5 seconds (array or scalar)
    t = np.asarray(t, float)
    return np.where(t < A4[0], A5[0] + (t - A4[0]) * s0, np.where(t > A4[-1], A5[-1] + (t - A4[-1]) * s1, np.interp(t, A4, A5)))


# grid model: v5 beats on a constant tempo
nidx = np.arange(len(b4))
cg = np.polyfit(nidx[good], anc[good, 0], 1)
gres = (anc[:, 0] - np.polyval(cg, nidx)) * 1e3
VER['beat_anchors'] = dict(n=int(len(b4)), used=int(good.sum()), median_r=float(np.median(anc[good, 1])),
                           v5_grid_bpm=float(60 / cg[0]), v5_grid_beat0=float(cg[1]),
                           grid_resid_ms_p50=float(np.median(np.abs(gres[good]))), grid_resid_ms_p95=float(np.percentile(np.abs(gres[good]), 95)),
                           offset_ms_min=float(off[good].min() * 1e3), offset_ms_max=float(off[good].max() * 1e3),
                           offset_ms_at=dict({f'{t:.0f}': round(float((m45(t) - t) * 1e3), 1) for t in [0, 6.78, 13.45, 28.53, 35, 45.2, 71.23, 89.77, 104.56, 134.09, 150, 164.1, 171.54, 200, 215, 227.2, 232]}))
print('beat anchors:', {k: v for k, v in VER['beat_anchors'].items() if k != 'offset_ms_at'})
print('offset t5-t4 (ms) at:', VER['beat_anchors']['offset_ms_at'])

# madmom on v5 vs mapped v4 beats
mm5 = np.load(P('mm_db_mix_v5.npy')); bb5, pp5 = mm5[:, 0], mm5[:, 1].astype(int)
mb = m45(b4); jj = np.clip(np.searchsorted(bb5, mb), 1, len(bb5) - 1)
jj = np.where(np.abs(bb5[jj - 1] - mb) < np.abs(bb5[jj] - mb), jj - 1, jj)
dd = (bb5[jj] - mb) * 1e3; inr = (b4 > 1) & (b4 < T['grid_end'])
VER['madmom_v5_vs_mapped_v4_beats'] = dict(n_v5=int(len(bb5)), n_v4=int(len(b4)), median_ms=float(np.median(dd[inr])),
                                           p95_abs_ms=float(np.percentile(np.abs(dd[inr]), 95)), max_abs_ms=float(np.abs(dd[inr]).max()),
                                           downbeat_phase_agree=float(np.mean(pp5[jj][inr] == np.array(T['beat_pos'])[inr])),
                                           note='madmom output is 10 ms quantised')
print('madmom v5 vs mapped:', VER['madmom_v5_vs_mapped_v4_beats'])

# ------------------------------------------------ 4. residual after warping: per-10 s window xcorr of v5 vs warped v4
tq = np.arange(len(ob)) / 100
inv = lambda t5: np.interp(t5, m45(np.arange(0, 233, 0.01)), np.arange(0, 233, 0.01))
oa_on5 = np.interp(inv(tq), np.arange(len(oa)) / 100, oa)   # v4 onset envelope resampled onto the v5 timeline
pa_on5 = np.interp(inv(np.arange(len(pb)) / 1000), np.arange(len(pa)) / 1000, pa)
VER['warped_windows_10s'] = []
for s in range(0, 230, 10):
    i0, i1 = s * 1000 + 300, min((s + 10) * 1000, len(pb) - 400)
    L, r, r0 = best_lag(pa_on5, pb, i0, i1, 60)
    VER['warped_windows_10s'].append(dict(t5=s, residual_lag_ms=round(L, 1), r=round(r, 3)))
print('residual after warp (1 ms env, per 10 s):', [(w['t5'], w['residual_lag_ms'], w['r']) for w in VER['warped_windows_10s']])


# ------------------------------------------------ 5. key events: measured locally (short-window xcorr) + energy edges
def edb(x, h=48, w=96): return 20 * np.log10(np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(w) / w, 'same')[::h] + 1e-14))


ea, eb = edb(a), edb(b)  # 1 ms mix level


def edge(e, t, rise, thr_db=10, search=0.35, w=25):
    """time of the largest level step (rise or fall) near t (1 ms env, step measured over +-w ms)."""
    i0, i1 = int((t - search) * 1000), int((t + search) * 1000)
    st = np.array([e[i:i + w].mean() - e[i - w:i].mean() for i in range(i0, i1)])
    k = int(np.argmax(st if rise else -st)); return (i0 + k) / 1000, float(st[k])


inst4 = sf.read(P('stems', 'no_vocals.wav'))[0].mean(1); inst5 = sf.read(P('stems_v5', 'no_vocals.wav'))[0].mean(1)
ei4, ei5 = edb(inst4), edb(inst5)
KEY = [('braam', 6.78, 'rise'), ('shot', 42.89, 'xc'), ('shot_sfx', 43.24, 'xc'), ('tapestop1', 43.42, 'xc'), ('silence1_start', 43.92, 'fall_i'),
       ('silence1_end', 45.12, 'rise_i'), ('drop1', 45.201, 'rise'), ('shot', 102.28, 'xc'), ('shot_sfx', 102.56, 'xc'),
       ('tapestop2', 102.84, 'xc'), ('silence2_start', 103.28, 'fall_i'), ('silence2_end', 104.45, 'rise_i'), ('drop2', 104.556, 'rise'),
       ('braam', 137.41, 'rise'), ('braam', 141.60, 'rise'), ('braam', 145.38, 'rise'), ('brk_dropout', 149.12, 'fall'),
       ('cut3', 170.62, 'fall'), ('digital_silence', 171.28, 'fall'), ('final_drop', 171.542, 'rise'), ('instrumental', 215.858, 'xc'),
       ('braam', 219.60, 'rise'), ('braam', 223.40, 'rise'), ('end_hit', 227.20, 'rise')]
VER['events'] = []
for name, t4, kind in KEY:
    pm = float(m45(t4))
    tx, rx = fine_at(t4, W=150, ML=80)
    row = dict(event=name, t4=t4, t5_map=round(pm, 4), t5_xcorr=round(tx, 4), xcorr_r=round(rx, 2))
    if kind != 'xc':
        e4, e5 = (ei4, ei5) if kind.endswith('_i') else (ea, eb)
        rise = kind.startswith('rise')
        g4, st4 = edge(e4, t4, rise); g5, st5 = edge(e5, pm, rise)
        row.update(edge_t4=g4, edge_t5=g5, edge_step_db=[round(st4, 1), round(st5, 1)], edge_t5_minus_map_of_edge_t4_ms=round((g5 - float(m45(g4))) * 1e3, 1))
    row['xcorr_minus_map_ms'] = round((tx - pm) * 1e3, 1)
    VER['events'].append(row)
    print(row)

# ------------------------------------------------ 6. vocal line starts on the separated vocal stems
v4v = sf.read(P('stems', 'vocals.wav'))[0].mean(1); v5v = sf.read(P('stems_v5', 'vocals.wav'))[0].mean(1)
ev4, ev5 = edb(v4v, 480, 960), edb(v5v, 480, 960)  # 10 ms


def onset_after(e, t, thr=-45, back=0.25):
    i = int((t - back) * 100)
    w = np.where(e[i:i + 100] > thr)[0]
    return (i + w[0]) / 100 if len(w) else np.nan


VER['lines'] = []
for li, l in enumerate(T['lines']):
    t4 = l['start']; pm = float(m45(t4))
    # vocal-stem envelope xcorr (window -0.3..+1.2 s around the line start, +-150 ms around the mapped time)
    i = int(t4 * 100); j0 = int(round(pm * 100)); u = ev4[i - 30:i + 120]
    rs = [zc(u, ev5[j0 + L - 30:j0 + L + 120]) for L in range(-15, 16)]
    k = int(np.argmax(rs)); d = 0.0
    if 0 < k < 30:
        den = rs[k - 1] - 2 * rs[k] + rs[k + 1]; d = 0.5 * (rs[k - 1] - rs[k + 1]) / den if den else 0
    tx = (j0 + k - 15 + d) / 100
    o4, o5 = onset_after(ev4, t4), onset_after(ev5, pm)
    VER['lines'].append(dict(line=li, text=l['text'], t4=t4, t5_map=round(pm, 3), t5_vocal_xcorr=round(tx, 3), r=round(float(rs[k]), 2),
                             xcorr_minus_map_ms=round((tx - pm) * 1e3, 1),
                             thr_onset_minus_map_ms=round(((o5 - float(m45(o4))) * 1e3) if np.isfinite(o4 + o5) else np.nan, 1)))
    print(VER['lines'][-1])

# ------------------------------------------------ 7. timing_v5.json
y2, _ = librosa.load(V5, sr=SR, mono=False); y = y2.mean(0); DUR = len(y) / SR
voc, inst = v5v, inst5
r3 = lambda t: round(float(m45(t)), 3)
D = json.loads(json.dumps(T))
D['source'] = 'Rewind (5).mp3'; D['duration'] = round(DUR, 3)
D['mapped_from'] = 'timing.json (Rewind (4).mp3) via time_map; hits/kicks/bpm recomputed on v5 audio; see TIMING_V5_NOTES.md'
D['grid_end'] = r3(T['grid_end'])
beats = np.round(m45(b4), 4)
D['beats'] = [float(x) for x in beats]
D['downbeats'] = [float(x) for x in beats[np.array(T['beat_pos']) == 1]]
D['bars'] = [dict(bar=i + 1, t=float(t)) for i, t in enumerate(D['downbeats'])]
db_ = np.array(D['downbeats'])
D['bar_bpm'] = [dict(bar=i + 1, t=float(db_[i]), bpm=round(float(240 / (db_[i + 1] - db_[i])), 2)) for i in range(len(db_) - 1)]
ibi = np.diff(beats)
D['bpm'] = round(float(60 / np.median(ibi[(beats[:-1] > 45) & (beats[:-1] < 215)])), 2)
D['bpm_note'] = 'v5 is conformed to a constant ~129.00 BPM grid (v4 drifted 126-130). Beats = v4 beats mapped through time_map.'
for s_ in D['sections']:
    s_['start'] = r3(s_['start']) if s_['start'] > 0 else 0.0
    s_['end'] = round(DUR, 3) if s_['name'] == 'end' else r3(s_['end'])
    m = (beats[:-1] >= s_['start']) & (beats[1:] <= s_['end'])
    s_['bpm'] = round(float(60 / np.median(ibi[m])), 2) if m.sum() >= 4 else None
for l in D['lines']: l['start'], l['end'] = r3(l['start']), r3(l['end'])
for w in D['words']: w['start'], w['end'] = r3(w['start']), r3(w['end'])
for e in D['events']:
    e['t'] = r3(e['t'])
    if 'end' in e: e['end'] = r3(e['end'])
for c in D['vocal_chops']: c['start'], c['end'] = r3(c['start']), r3(c['end'])
# kicks: map, then re-snap to the v5 30-90 Hz onset (+-40 ms) exactly like build_timing.py
sos = ss.butter(4, [30, 90], 'band', fs=SR, output='sos'); sub = ss.sosfiltfilt(sos, y)
sdb = edb(sub, 48, 96); sfl = np.maximum(0, np.diff(sdb, prepend=sdb[0]))
kk = []
for t in m45(np.array(T['kicks'])):
    i = int(t * 1000); w = sfl[i - 40:i + 40]; kk.append(round((i - 40 + int(np.argmax(np.convolve(w, np.ones(5), 'same')))) / 1000, 3))
D['kicks'] = kk
VER['kicks_resnap_minus_map_ms'] = dict(median=float(np.median((np.array(kk) - m45(np.array(T['kicks']))) * 1e3)),
                                        p95_abs=float(np.percentile(np.abs((np.array(kk) - m45(np.array(T['kicks']))) * 1e3), 95)))

# ------------------------------------------------ 8. envelopes_v5.json (identical method to build_timing.py) + hits
FPS = 30; NF = int(np.ceil(DUR * FPS)); hop = SR // FPS; nfft = 4096
Sx = np.abs(librosa.stft(y, n_fft=nfft, hop_length=hop, center=True))[:, :NF]
fr = librosa.fft_frequencies(sr=SR, n_fft=nfft)
band = lambda lo, hi: 10 * np.log10((Sx[(fr >= lo) & (fr < hi)] ** 2).sum(0) + 1e-10)
frame_rms = lambda x: 20 * np.log10(librosa.feature.rms(y=x, frame_length=3200, hop_length=hop, center=True)[0][:NF] + 1e-7)
NORM = {}


def nz(name, xdb, floor_pct=1, top_pct=99.7, floor_abs=None):
    lo = np.percentile(xdb, floor_pct) if floor_abs is None else floor_abs; hi = np.percentile(xdb, top_pct)
    NORM[name] = (float(lo), float(hi)); return np.clip((xdb - lo) / (hi - lo), 0, 1)


RAW = dict(rms=frame_rms(y), low=band(20, 150), mid=band(150, 2000), high=band(2000, 16000), vocal=frame_rms(voc.astype(np.float32)), inst=frame_rms(inst.astype(np.float32)))
env = {'rms': nz('rms', RAW['rms'], floor_abs=-60), 'low': nz('low', RAW['low'], 5), 'mid': nz('mid', RAW['mid'], 5), 'high': nz('high', RAW['high'], 5),
       'vocal': nz('vocal', RAW['vocal'], floor_abs=-50), 'inst': nz('inst', RAW['inst'], floor_abs=-60)}
oh = 192
oe = librosa.onset.onset_strength(y=y, sr=SR, hop_length=oh, n_mels=128); ot = np.arange(len(oe)) * oh / SR
of = np.zeros(NF); np.maximum.at(of, np.minimum((ot * FPS + 0.5).astype(int), NF - 1), oe)
env['onset'] = np.clip(of / np.percentile(of, 99.7), 0, 1)
pk, _ = ss.find_peaks(oe, distance=int(0.09 * SR / oh), prominence=np.percentile(oe, 95))
Sm = np.abs(librosa.stft(y, n_fft=2048, hop_length=oh)); fm = librosa.fft_frequencies(sr=SR, n_fft=2048)
flux = np.maximum(0, np.diff(np.log1p(Sm), axis=1, prepend=np.log1p(Sm[:, :1])))
bands_ = {'low': (fm < 150), 'mid': (fm >= 150) & (fm < 2000), 'high': fm >= 2000}
top = np.percentile(oe[pk], 99) if len(pk) else 1
D['hits'] = [dict(t=round(float(ot[p]), 3), s=round(float(min(1, oe[p] / top)), 3),
                  band=max(bands_, key=lambda k_: float(flux[bands_[k_], p].sum()))) for p in pk]
D['time_map'] = dict(v4=[round(float(x), 4) for x in A4], v5=[round(float(x), 4) for x in A5],
                     slope_before=round(float(s0), 6), slope_after=round(float(s1), 6),
                     usage='t5 = interp(t4, v4, v5); linear extrapolation with slope_before/slope_after outside; inverse = interp(t5, v5, v4)')
import re
_num = lambda m: (f"{float(m45(float(m.group(0)))):.{len(m.group(0).split('.')[1])}f}" if 1.0 <= float(m.group(0)) <= 233 else m.group(0))
for coll in (D['sections'], D['events']):
    for x in coll:
        if x.get('note'): x['note'] = re.sub(r'(?<![\d.])\d{1,3}\.\d{1,3}(?![\d.])', _num, x['note'])   # times in notes -> v5
json.dump(D, open(P('timing_v5.json'), 'w'), indent=1, ensure_ascii=False)
json.dump(dict(fps=FPS, n_frames=NF, duration=round(DUR, 3), source='Rewind (5).mp3',
               desc=dict(rms='mix RMS dB, -60dB..p99.7 -> 0..1', low='20-150 Hz band energy (sub/kick)', mid='150-2000 Hz', high='2-16 kHz',
                         vocal='vocal-stem RMS, -50dB..p99.7', inst='instrumental-stem RMS', onset='mel spectral-flux onset strength, max-pooled per frame'),
               frame_time='frame i is centred at t = i/30 s (v5 time)',
               **{k_: [round(float(v), 3) for v in arr] for k_, arr in env.items()}),
          open(P('envelopes_v5.json'), 'w'), separators=(',', ':'))

# ------------------------------------------------ 9. level differences by section (v5 vs v4, time-aligned)
a_l, _ = librosa.load(V4, sr=SR, mono=True)
rms = lambda x: 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)
V4voc, V4inst = v4v, inst4
LV = []
for s4, s5 in zip(T['sections'], D['sections']):
    A_, B_ = slice(int(s4['start'] * SR), int(s4['end'] * SR)), slice(int(s5['start'] * SR), int(s5['end'] * SR))
    row = dict(section=s4['name'], mix_v4=round(rms(a_l[A_]), 1), mix_v5=round(rms(y[B_]), 1))
    row['mix_d'] = round(row['mix_v5'] - row['mix_v4'], 1)
    row['inst_d'] = round(rms(inst5[B_]) - rms(V4inst[A_]), 1); row['voc_d'] = round(rms(v5v[B_]) - rms(V4voc[A_]), 1)
    LV.append(row)
VER['levels_by_section_dB'] = LV
VER['norm_v5'] = NORM
for r in LV: print(r)
json.dump(VER, open(P('v5_verify.json'), 'w'), indent=1, default=float)
print('wrote timing_v5.json envelopes_v5.json v5_verify.json; bpm', D['bpm'])
