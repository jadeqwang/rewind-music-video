#!/usr/bin/env python3
"""Rewind5_final_v3 = Rewind5_final with the intro rewind SFX ("the bats") spun down instead of hard-stopped.

Needs: assets/sound/Rewind5_intro_clean.wav (declick_intro.py --v5), intro_sfx5.wav (the v5 stem used for Rewind5_final) and
       intro_sfx5_taper.wav = make_intro_sfx.py --song "Rewind (5).mp3" --timing analysis/timing_v5.json --tag 5_taper --stem-only --taper 3.6 5.4
The tapered stem differs from intro_sfx5 by <1e-9 before 3.4 s (FFT round-off in the side-chain), so the original stem samples are used
before SPLICE -> v3 is bit-identical to Rewind5_final outside [SPLICE, end of the taper].
Also writes the recording guide for the "show them" pickup: recording_guide_28-48s.mp3 (bars 16-27, 28.047-48.497 s v5) and
recording_guide_28-48s_click.mp3 (2-bar count-in + click on every beat, accent on downbeats, 129 BPM grid of timing_v5.json).
"""
import os, json, subprocess, numpy as np, soundfile as sf
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000
D = os.path.join(ROOT, "assets/sound"); PV = os.path.join(D, "preview")
SPLICE = 3.3
rd = lambda n: sf.read(os.path.join(D, n), dtype="float32")[0]
clean, s5, st, final = rd("Rewind5_intro_clean.wav"), rd("intro_sfx5.wav"), rd("intro_sfx5_taper.wav"), rd("Rewind5_final.wav")


def add_sfx(x, stem):
    x = x.copy(); x[:len(stem)] = (x[:len(stem)].astype(np.float64) + stem).astype(np.float32); return x


def mp3(x, path, a=None, b=None, fade=0.3):
    xx = x[int(a * SR):int(b * SR)].copy() if a is not None else x
    if a is not None and fade: n = int(fade * SR); xx[-n:] *= np.linspace(1, 0, n)[:, None]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "320k", path],
                   input=xx.astype(np.float32).tobytes(), check=True)


assert np.array_equal(add_sfx(clean, s5).view(np.uint32), final.view(np.uint32)), "Rewind5_final is not clean + intro_sfx5"
stem = st.copy(); n0 = int(SPLICE * SR); stem[:n0] = s5[:n0]
print("max |taper - original stem| before splice: %.2e, at splice: %.2e" % (np.abs(st[:n0] - s5[:n0]).max(), np.abs(st[n0] - s5[n0]).max()))
v3 = add_sfx(clean, stem)
nz = np.nonzero(np.any(v3.view(np.uint32) != final.view(np.uint32), axis=1))[0]
null = dict(len_equal=v3.shape == final.shape, first_diff_s=round(nz[0] / SR, 4), last_diff_s=round(nz[-1] / SR, 4),
            identical_outside_3_6s=bool(nz[0] >= 3 * SR and nz[-1] < 6 * SR))
print("null vs Rewind5_final:", null)
rms = lambda x, a, b: round(float(20 * np.log10(np.sqrt(np.mean(x[int(a * SR):int(b * SR)].astype(np.float64) ** 2)) + 1e-12)), 1)
lv = {f"{t:.1f}": [rms(s5, t, t + 0.1), rms(stem, t, t + 0.1)] for t in np.arange(3.4, 5.7, 0.2)}
print("stem RMS dB per 100 ms [v2 hard stop, v3 taper]:", lv)
sf.write(os.path.join(D, "Rewind5_final_v3.wav"), v3, SR, subtype="FLOAT"); mp3(v3, os.path.join(D, "Rewind5_final_v3.mp3"))
mp3(v3, os.path.join(PV, "v5_final_v3_0-10s.mp3"), 0, 10)

# ---- recording guide (bars 16-27 around "I reach for my ID to show them and I do")
T = json.load(open(os.path.join(ROOT, "analysis/timing_v5.json")))
db_ = np.array(T["downbeats"]); A, B = float(db_[np.argmin(np.abs(db_ - 28))]), float(db_[np.argmin(np.abs(db_ - 48.5))])
beats = np.array(T["beats"]); bt = beats[(beats >= A - 1e-3) & (beats < B - 1e-3)]; P = float(np.median(np.diff(bt)))
ex = v3[int(round(A * SR)):int(round(B * SR))]
mp3(ex, os.path.join(D, "recording_guide_28-48s.mp3"), fade=0)
def click(accent):
    n = int(0.03 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * (2400 if accent else 1600) * t) * np.exp(-t / 0.006) * 10 ** ((-10 if accent else -14) / 20))
cin = 8 * P; L = int(round((cin + B - A) * SR)); out = np.zeros((L, 2), np.float32)
out[int(round(cin * SR)):int(round(cin * SR)) + len(ex)] = ex
ticks = [(cin - (8 - i) * P, i % 4 == 0) for i in range(8)] + [(cin + b - A, abs(b - db_).min() < 0.01) for b in bt]
for t0, acc in ticks:
    c = click(acc); i = int(round(t0 * SR)); out[i:i + len(c)] += c[:L - i, None]
mp3(out, os.path.join(D, "recording_guide_28-48s_click.mp3"), fade=0)
lines = [dict(text=l["text"], start=l["start"], end=l["end"]) for l in T["lines"][3:6]]
words = [dict(w=w["w"], start=w["start"], end=w["end"]) for w in T["words"] if w["line_idx"] == 4]
guide = dict(excerpt_song_start=A, excerpt_song_end=B, bars=[16, 27], bpm=round(60 / P, 3), beat_period=P,
             click_file_count_in_s=round(cin, 4), click_file_song_offset="song time = file time - %.4f + %.4f" % (cin, A),
             plain_file_song_offset="song time = file time + %.4f" % A, lines=lines, line4_words=words,
             them_slot=dict(note='"them" belongs on the beat at 37.816 (between "show" 37.20-37.66 and "and" 37.97/38.26); original pitch target: B4 like "Shore" (22.9 s)'))
json.dump(guide, open(os.path.join(D, "recording_guide_28-48s.json"), "w"), indent=1)
json.dump(dict(null=null, stem_rms_hard_vs_taper=lv), open(os.path.join(D, "v5_final_v3_stats.json"), "w"), indent=1)
print(json.dumps(guide, indent=1)[:600])
