# Intro SFX — OPTIONAL A/B variant (the song itself is untouched)

`Rewind (4).mp3` stays the default master. This folder holds a variant with subtle sound design for the cold-open
hook only (0–6.8 s); pick it or ignore it.

| file | what |
|---|---|
| `intro_sfx.wav` (gitignored) / `intro_sfx.mp3` | the SFX stem, 7.0 s, 48 kHz stereo (wav = float32) |
| `Rewind_with_intro_sfx.wav` (gitignored, float32) / `.mp3` (320k) | full song + stem. Mixing happens only in 0–7.0 s |
| `spectrogram_0-8s.png` | original / variant / stem, 0–8 s |
| `gen/` | ElevenLabs music-v2 tests (`rw_a`, `rw_b`, `tick_a`), the alternate stem with the EL whir, and stats |

Rebuild: `python3 tools/sound/make_intro_sfx.py` (add `--el-whir` for the ElevenLabs-whir alternate), then `python3 tools/sound/compare_intro.py`.

## Layers (synced to render/src/shots.js H0/H1)
- **0.00–0.594 s, freeze (H0 tableau):** the song's own gunshot noise burst (43.24–43.48 s), run through a synthetic 2.4 s reverb with a faint E2/E3/B3 comb, then **reversed**. It plays as an airy swell that is cut off on the bt(1) jerk.
- **0.594–4.406 s, rewind (H1_scrub):** a granular **reverse scrub of the song itself** that follows the visual playhead (226.7 s → 13.45 s, about ×56). Each 46 ms grain is reversed and sped up, with a pitch factor that rises from ×2.5 to ×9. The grains are band-limited to 350 Hz–7 kHz and spread slightly in stereo. Under them sits a synthetic tape-transport motor (a 70 → 330 Hz glide with flutter and reel wobble) plus tape hiss that rises. The level ramps up, and everything **stops hard** at bt(9) = 4.406 s with a small transport clunk (95 Hz, −34 dB).
- 4.5–6.8 s: nothing. The rain and kalimba play alone into the 6.78 braam.

## Kalimba protection and levels
- A spectral side-chain in the STFT holds the stem **≥ 6 dB under the song, bin by bin**, from 220 to 3000 Hz (tapered to 130 Hz and 6.5 kHz), which covers the kalimba fundamentals and overtones. The result: in the kalimba band the song sits 12 dB above the stem at the worst frame and 23 dB above at the median. The stem's audible content therefore lives in the gaps, below about 200 Hz (motor) and above about 4 kHz (chatter and hiss).
- RMS stem vs song: 0–0.6 s −54.9 vs −39.1 dB; 0.6–2 s −49.4 vs −30.3 dB; 2–4.4 s −37.1 vs −22.0 dB. Stem peak −20.7 dBFS.
- −1 dBTP limiter (4× oversampled) on 0–6.8 s only. It is inactive because the touched region peaks at −8.4 dBTP (wav) and −8.5 dBTP (mp3).

## Null test (`tools/sound/compare_intro.py`)
- Variant wav vs the ffmpeg float decode of the original: same length (11 155 200 samples). The two are **bit-identical from 7.0 s**, and the last differing sample is at 4.496 s.
- The mp3 is a lossy re-encode, so it can't be bit-identical. Its residual after 7 s is −56.6 dBFS RMS (−40 dB relative). For the video, use the wav, or use the original mp3 after 7 s.

## ElevenLabs music-v2 comparison (cost about $0.03)
`rw_a` was mostly quiet with clicks, so it went unused. `tick_a` was a tonal pad rather than a tick, and its key wasn't controlled, so it also went unused. `rw_b` (a rising harmonic whir) was the best of the three. It's in `gen/intro_sfx_alt_elevenlabs_whir.mp3` and `gen/spectrogram_0-8s_elwhir.png`. Its harmonics sit inside the kalimba band, so the side-chain removes most of them and its rise is lost. The self-made motor glides below the kalimba instead, which is why it's the default.

## v2: intro percussive hit removed (user request) + the intro SFX
`Rewind_v2_intro_clean.wav` (gitignored, float32) and `.mp3` are built by `python3 tools/sound/declick_intro.py [c1|c1b]` (the default is c1).
The script needs `intro_sfx.wav`, so run `make_intro_sfx.py` first.

**Percussive candidates in 0–13.45 s** (HPSS margin 2, spectral flux, band energies):
| id | time | what | level |
|---|---|---|---|
| **c1** | **6.78–~10 s** | THE hit: a sub boom (20–150 Hz, +45 dB over the pre-hit level, decays until about 10 s) plus a broadband roll/smash from 6.78 to 7.75 s (3–16 kHz) | mix RMS (20 ms) jumps from −30 to −15 dBFS; peak −11.4 dBFS |
| c1b | 6.78–7.75 s | the same event with only the >150 Hz roll removed, keeping the sub swell ("braam") | |
| (rejected) | 2.87–3.35, 9.66–11.6 s | the HPSS "percussive" peaks are kalimba note attacks (800–4 kHz) | perc −27 to −33 dB |
| (rejected) | 0–13 s | 16th-note HF tick pulse (8–20 kHz, about every 0.119 s), continuous texture | |
| our SFX | 4.406 s clunk, 0.594 s cut | 20 dB under the song at those instants, so not a loud percussive element | −48 vs −28 dB (10 ms RMS) |

**Method:** a per-bin spectral cap toward the pre-hit texture. Every STFT bin in the window is capped at its 92nd percentile
over 4.45–6.74 s (the same kalimba, drone, rain and ticks, with no hit), plus 2 dB. Content that is already present before the hit passes at unity gain.
The cap fades out over 8.6–10.4 s, and the original is spliced back with a 20 ms crossfade. The vocal stem is about −61 dB here,
so the mix is processed directly. Re-summing the separated stems would only have added separation artifacts.

**Null test:** the edit ends at 10.6 s. The last differing sample is at 10.416 s, and the file is **bit-identical** to the original after that (same length).
True peak over 0–14 s is −7.96 dBTP. Previews of 0–14 s, all with the intro SFX: `preview/00_reference_original_plus_sfx_0-14s.mp3`,
`preview/c1_06.78_impact_full_0-14s.mp3` and `preview/c1b_06.78_roll_only_0-14s.mp3`. Before/after spectrogram: `spectrogram_v2_intro_clean_0-14s.png`.
The video's title card (H3_title) still cuts on 6.78. With c1 that cut happens on a quiet moment.

## v5 ("Rewind (5).mp3"): use `Rewind5_final` for the final encode
v5 is **re-timed** against v4: it's conformed to a constant 129 BPM, so t5 - t4 runs from -483 to +86 ms (see `analysis/TIMING_V5_NOTES.md`).
Every v5 file here is built on the v5 timeline from `analysis/timing_v5.json`. The intro beats are bt(1) = 0.5815 and bt(9) = 4.3106, the impact is at 6.635, the gunshot burst at 42.793, and the scrub runs 226.62 -> 13.154.

| file | what |
|---|---|
| `Rewind5_final.wav` (gitignored, float32) / `.mp3` (320k) | **master**: v5 with the 6.6 s impact removed (c1 method) plus the intro SFX |
| `Rewind5_final_soft.wav` / `.mp3` | alternate: the impact is kept at -12 dB (`clean + 0.25 x removed`) plus the intro SFX |
| `Rewind5_intro_clean.wav` / `.mp3` | impact removed, no SFX |
| `Rewind5_with_intro_sfx.wav` / `.mp3` | v5 plus the intro SFX only (the impact is untouched) |
| `intro_sfx5.wav` / `.mp3` | the SFX stem rebuilt on v5 timing (6.855 s) |
| `preview/v5_original_0-14s.mp3`, `v5_with_intro_sfx_`, `v5_final_`, `v5_final_soft_` | 0-14 s previews |
| `spectrogram_v5_final_0-14s.png`, `v5_intro_stats.json` | before/after and numbers |

Rebuild:
1. `python3 tools/sound/make_intro_sfx.py --song "Rewind (5).mp3" --timing analysis/timing_v5.json --tag 5`, then convert to mp3 with ffmpeg (libmp3lame 320k).
2. `python3 tools/sound/declick_intro.py --v5 [--soft-db 12]`.

The v4 defaults are unchanged. One difference: reading the constants from timing.json now gives a 1-sample-longer gunshot burst, which differs from the old v4 build by at most 1e-6.

**The impact in v5:** her mutes reduced it by about 4-6 dB, but it is still clearly there:

| version | sub 20-150 (0-2.5 s) over pre-hit | 150-3k (0-1 s) | 3-16k (0-0.97 s) | mix RMS 0-1 s over pre | mix peak |
|---|---|---|---|---|---|
| v4 | +42.9 dB | +7.7 | +14.1 | +11.0 | -7.0 dBFS |
| v5 | +38.6 (-25.8 dBFS) | +1.3 | +14.4 (-43.6 dBFS) | +4.5 | -9.6 |
| v5 clean (final) | +9.4 (-55.0 dBFS) | -1.1 | +4.9 (-53.1 dBFS) | -1.0 | -13.2 |
| v5 soft (-12 dB) | +27.3 (-37.1 dBFS) | -0.7 | +8.1 | -0.1 | -12.8 |

In the full removal, the 150-800 Hz texture during 7.0-8.5 s ends up 2-3.6 dB under the v5 original. Part of that is the impact's own low-mid tail, and part is kalimba notes that weren't in the reference window. The soft variant fills that dip back in, but it keeps an audible sub swell (-37 dBFS).

**Null tests:** all three edited files have the same length as the v5 decode and are **bit-identical to v5 from 10.367 s** (the last differing sample is at 10.192 s). The removal starts at 6.557 s. `Rewind5_with_intro_sfx.wav` is bit-identical from 6.855 s (the last difference is at 4.40 s). True peak over 0-14 s is -5.1 dBTP, because v5 is about 2 dB hotter than v4. The mp3s are lossy re-encodes; use the wav for the mux if possible.

## v5 final v2: "show (them) and I do" (`tools/sound/insert_them.py`, `verify_them.py`)
`Rewind5_final_v2.wav` / `.mp3` is `Rewind5_final` with the sung word "them" added at 37.72-38.25 s (v5 time). The vowel starts on the beat at 37.816, and the word ends before "and" at 38.26.
- **How it's built:** WORLD vocoder resynthesis of her own phonemes from the v5 vocal stem. Formants and aperiodicity are kept.
  - /ð/ is the whispered "th" hiss of "The".
  - /ɛm/ is the ɛ+m of "dreamt", taken before the t.
  - The f0 is the measured contour of "Shore" (22.915 s): a scoop on A4, then B4 at -21 cents. Its timing relative to the vowel onset is kept.
  - Level matched to "show"; octave-smoothed tilt EQ (±4 dB); L/R balance of "show".
  - Ducked synthetic room tail (wet at 10 % while the word sounds), calibrated to "show"'s release tail (-16 dB).
- **How it's mixed:** the word is added on top of the full mix. The file is bit-identical to `Rewind5_final.wav` outside 37.718-39.316 s.
- **Variants:** B = master (/ð/ from the reprise "The" at 147.67, ɛm from the reprise "dreamt" at 158.06). A = ð from the reprise + ɛm from verse-1 "dreamt" (24.07). C = ð from verse-1 "The" (13.77) + verse-1 ɛm. Files: `Rewind5_final_v2A.wav`, `Rewind5_final_v2C.wav`.
- **Previews:** `preview/them_before_30-45s.mp3`, `them_after_30-45s.mp3` (B), `them_after_A_30-45s.mp3`, `them_after_C_30-45s.mp3`.
- **Plot:** `them_insert_spectrogram_f0.png`.
- **Checks:** run on the re-separated 30-45 s; numbers in `analysis/them/verify.json`.
  - **B (master):** f0 error median 11 cents, p90 50 cents. B4 sustain is 490.2 Hz, the same as "Shore" (0 cents).
  - **Sustain purity:** the fundamental sits 19 dB over the A4 region, against 19.5-27.6 dB on the real "Shore".
  - **Loudness:** LUFS-M is -20.8 vs "show" -20.9 and "and" -20.7.
  - **Cepstral distance:** to "show" 91, against the natural show-to-"and" distance of 92.
  - **Splices:** spectral flux at the joins is 96-178, within the 61-249 range of the line's natural onsets.
  - **Caveat:** the vowel is spectrally further from the source "dreamt" ɛ (about 106, against 47 between the two real "dreamt"s). This comes from the +9 semitone shift (D4 -> B4). Listen for "them" sounding thin or synthetic.

**Dropped (user verdict):** all three "them" variants sound distorted/funny. Keep `Rewind5_final_v2*` and `analysis/them/` for reference only; don't use them. She'll record the line herself.

## v5 final v3: intro rewind SFX tapered (the master; no "them")
`Rewind5_final_v3.wav` (gitignored) / `.mp3`: `Rewind5_final` with the reversed-grain chatter + motor ("the bats") spun down instead of hard-stopped at bt(9) = 4.31 s (v5).
- **Fade:** equal-power from 3.6 s to silence at 5.4 s.
- **Tape slowing down over the same span:** playhead speed and grain pitch drop to ×0.5. Grain density thins (each grain is kept with probability speed²). The motor glide slows too. A time-varying low-pass closes from 12 kHz to 3 kHz.
- **Clunk:** −12 dB vs before, moved to the end of the spin-down (5.4 s).
- **Stem RMS per 100 ms:** −34 dB (3.6 s), −39 (4.4), −47 (4.8), −56 (5.2), −60 (5.4), then silence. Before, it went from −34 to silence at 4.31.
- **Rebuild:** `make_intro_sfx.py --song "Rewind (5).mp3" --timing analysis/timing_v5.json --tag 5_taper --stem-only --taper 3.6 5.4`, then `tools/sound/build_final_v3.py`.
- **Null test:** bit-identical to `Rewind5_final.wav` except 3.490–5.490 s (same length). Before 3.3 s the original stem samples are used. Numbers are in `v5_final_v3_stats.json`.
- **Preview:** `preview/v5_final_v3_0-10s.mp3` (compare with `preview/v5_final_0-14s.mp3`).

## Recording guide for "I reach for my ID to show them and I do"
- **Full song:** `Rewind5_final_v3.mp3`.
- **`recording_guide_28-48s.mp3`:** bars 16–27 of v3. Song time = file time + 28.047.
- **`recording_guide_28-48s_click.mp3`:** a 2-bar count-in click (3.725 s), then the same excerpt with a click on every beat (accent on downbeats, ~129 BPM). Song time = file time − 3.725 + 28.047.
- **`recording_guide_28-48s.json`:** line and word times. "show" is at 37.20–37.66 s and "them" belongs on the beat at 37.816. "and" starts at ~38.0 (its vowel lands on the 38.285 beat). The line starts at 35.448 and ends at 39.275.
