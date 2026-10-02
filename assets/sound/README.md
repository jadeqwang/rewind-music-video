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
