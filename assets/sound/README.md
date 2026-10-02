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
