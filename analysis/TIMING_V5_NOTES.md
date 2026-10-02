# Rewind (5) vs Rewind (4): timing + level check

Produced by `analysis/build_timing_v5.py` (numbers in `analysis/v5_verify.json`). v5 = "Rewind (5).mp3", decoded length 232.249 s (v4 232.400 s). Both files have the same mp3 start offset, so the length difference isn't a decoder artefact.

## Verdict: the timing DID change

v5 is v4 **conformed to a constant 128.999 BPM grid** (DAW-style warp). v4 drifts 126 -> 130 BPM; v5 is flat at 129. Measured beat anchors fit `t5 = 0.1268 + n * 0.465118` (beat n of timing.json) with a median residual of 2.7 ms (p95 14.2 ms; the larger residuals are in the sparse intro and build 1 and come from where v4's beats sit). Because of that, the offset t5 - t4 is not constant. It drifts smoothly:

| v4 time | 0 | 6.78 braam | 13.45 verse1 | 28.5-35 | 45.20 drop1 | 71.2 | 89.8 | 104.56 drop2 | 134.1 | 150 | 164.1 | 171.54 final drop | 200 | 215 | 227.20 end | 232 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t5 - t4 (ms) | -0 | -145 | -298 | -483 | -432 | -397 | -342 | -244 | -25 | -121 | -242 | -251 | -33 | +84 | -76 | -164 |

Range: **-483 ms to +86 ms**. The largest deviation is at ~27-38 s (build 1), where v5 is 0.48 s early. Every audible sync point in the video would drift by up to half a second, so the video needs `timing_v5.json`.

## Method / evidence

1. **Naive onset-envelope cross-correlation at 100 Hz** (whole track): there is no dominant peak (best r = 0.12 at -410 ms, r = -0.02 at 0 lag). Per-10 s windows give lags anywhere from -0.8 s to +0.76 s with r 0.15-0.9. A constant offset is ruled out; the loopy material aliases to bar/beat multiples when the search is wide.
2. **Banded DTW** (mel dB + per-band spectral flux, 100 Hz, ±1 s band) gives a smooth warp path. **Fine anchors**: for each of the 499 v4 beats, a 1 ms onset-envelope cross-correlation (±250 ms window, ±60 ms search around the DTW path) measures the v5 time. 485/499 anchors were kept (median r 0.95; rejects had r < 0.4 or were > 15 ms off a 7-beat median). These anchors are `time_map` in timing_v5.json.
3. **madmom on v5** (same RNN+DBN settings, `madmom_db_v5.py`) finds 498 beats. They match the mapped v4 beats with a median of -1.4 ms, p95 13 ms and max 38 ms (madmom output is 10 ms quantised). **Downbeat phase agrees 100 %**, so the bar numbering is unchanged.
4. **After warping**, every 10 s window has a residual lag of |0.6| ms or less (1 ms envelope, r >= 0.93). The map is exact to about 1 ms across the whole track.
5. **Key events** were measured independently with a ±150 ms window cross-correlation. All of them are within 3.3 ms of the map:

| event | v4 | v5 (map) | v5 measured | diff ms |
|---|---|---|---|---|
| braam | 6.780 | 6.635 | 6.633 | -2.1 |
| shot | 42.890 | 42.441 | 42.443 | +2.4 |
| shot_sfx | 43.240 | 42.794 | 42.795 | +1.2 |
| tapestop1 | 43.420 | 42.975 | 42.975 | -0.3 |
| silence1_start | 43.920 | 43.480 | 43.481 | +1.5 |
| silence1_end | 45.120 | 44.687 | 44.688 | +0.3 |
| drop1 | 45.201 | 44.769 | 44.769 | +0.2 |
| shot | 102.280 | 102.020 | 102.020 | -0.1 |
| shot_sfx | 102.560 | 102.301 | 102.304 | +3.3 |
| tapestop2 | 102.840 | 102.582 | 102.581 | -1.2 |
| silence2_start | 103.280 | 103.026 | 103.026 | -0.5 |
| silence2_end | 104.450 | 104.205 | 104.205 | +0.1 |
| drop2 | 104.556 | 104.312 | 104.311 | -1.0 |
| braam | 137.410 | 137.367 | 137.366 | -0.4 |
| braam | 141.600 | 141.532 | 141.531 | -0.4 |
| braam | 145.380 | 145.284 | 145.284 | +0.1 |
| brk_dropout | 149.120 | 148.993 | 148.993 | +0.3 |
| cut3 | 170.620 | 170.360 | 170.360 | +0.2 |
| digital_silence | 171.280 | 171.026 | 171.024 | -1.7 |
| final_drop | 171.542 | 171.291 | 171.291 | +0.2 |
| instrumental | 215.858 | 215.943 | 215.940 | -3.1 |
| braam | 219.600 | 219.652 | 219.652 | +0.0 |
| braam | 223.400 | 223.400 | 223.400 | +0.1 |
| end_hit | 227.200 | 227.124 | 227.123 | -0.7 |

   Energy-step edges agree within ±7 ms wherever the step is strong (drops, braams, cut3, final drop, end hit). The weak steps (silence1 start at -2.9 dB, the breakdown drop-out at -3.3 dB) aren't reliable edges; for those, the cross-correlation is the measurement.
6. **Vocals**: v5 was separated with the same UVR MDX `Kim_Vocal_2` model (`separate_mdx.py "../Rewind (5).mp3" stems_v5`). The cross-correlation of the vocal-stem envelope at each lyric line start agrees with the map within **12.2 ms** (10 ms envelope; r 0.73-0.99):

| # | line | v4 | v5 | measured - map ms |
|---|---|---|---|---|
| 0 | The night before my dissertation d | 13.55 | 13.25 | -12.0 |
| 1 | I'm speeding down Lake Shore, I dr | 21.12 | 20.70 | -9.4 |
| 2 | a shadow chasing me I couldn't pla | 25.68 | 25.21 | -6.2 |
| 3 | I pulled over, and men in shades a | 29.56 | 29.08 | +0.3 |
| 4 | I reach for my ID to show … and I  | 35.93 | 35.45 | -1.8 |
| 5 | With no warning I get shot … and t | 40.57 | 40.11 | +2.5 |
| 6 | Rewind. | 52.26 | 51.85 | +0.9 |
| 7 | Rewind. | 56.00 | 55.59 | -1.7 |
| 8 | And now I'm back on the road | 73.55 | 73.16 | +9.8 |
| 9 | sirens in my mirror …Reload. | 80.57 | 80.19 | -9.1 |
| 10 | A shadow chasing me like it's a ra | 85.07 | 84.71 | +2.4 |
| 11 | I zigzag across the field of grass | 88.92 | 88.57 | -4.8 |
| 12 | they chase me and they're just too | 95.25 | 94.94 | +3.0 |
| 13 | With no warning I get shot … and t | 99.95 | 99.67 | +0.8 |
| 14 | Rewind. | 112.14 | 111.95 | +1.9 |
| 15 | Rewind. | 115.72 | 115.56 | +3.0 |
| 16 | The night before my dissertation d | 147.82 | 147.71 | -12.2 |
| 17 | I'm speeding down Lake Shore, I dr | 154.75 | 154.58 | -4.5 |
| 18 | a shadow chasing me I couldn't pla | 159.37 | 159.16 | -2.9 |
| 19 | Never stop. | 169.77 | 169.51 | -5.1 |

**Max deviation of the v4->v5 map from any measurement: 3.3 ms on events and 12 ms on vocal line starts (10 ms resolution).** That is below one video frame (33 ms).

## Files

- `analysis/timing_v5.json`: same schema as timing.json, on the v5 timeline. Beats, downbeats, bars, sections, lines, words, events and vocal_chops are mapped (times inside `note` strings are mapped too). `kicks` were re-snapped to the v5 30-90 Hz onset and `hits` recomputed on the v5 audio. `bpm`/`bar_bpm`/section bpm were recomputed (median 129.03). `duration` = 232.249. Also added: `time_map` {v4[], v5[], slope_before, slope_after}.
- **Mapping function**: `t5 = np.interp(t4, tm['v4'], tm['v5'])`; inverse `t4 = np.interp(t5, tm['v5'], tm['v4'])`. Outside the anchors, extrapolate linearly with slope_before/slope_after. JS: the same piecewise-linear lookup over the two arrays.
- `analysis/envelopes_v5.json`: same format/method as envelopes.json, computed on the v5 audio and v5 stems. Each key is normalised to its own percentiles exactly as before, so the 0..1 ranges stay comparable; the balance changes below show up as relative differences. n_frames 6968.
- `analysis/stems_v5/{vocals,no_vocals}.wav` (gitignored), `analysis/mm_db_mix_v5.npy`, `analysis/v5_verify.json`.

## Level differences (v5 - v4, time-aligned sections, RMS dB)

| section | mix | instrumental stem | vocal stem |
|---|---|---|---|
| intro | -1.1 | -1.1 | +0.3 |
| verse1 | +2.2 | +2.0 | +2.4 |
| build1 | +2.0 | +1.4 | +3.1 |
| tapestop1 | +3.6 | +0.3 | +4.5 |
| silence1 | +2.3 | +1.6 | +2.5 |
| drop1 | +2.4 | +2.2 | +4.5 |
| verse3 | +2.1 | +1.6 | +4.4 |
| build2 | +1.6 | +1.1 | +3.5 |
| tapestop2 | +3.7 | -1.3 | +5.2 |
| silence2 | +3.1 | +2.2 | +3.3 |
| drop2 | +1.6 | +1.4 | +4.8 |
| breakdown | +2.7 | +2.6 | +3.7 |
| build3 | +0.7 | +0.0 | +3.2 |
| silence3 | +3.1 | -0.5 | +3.2 |
| final_drop | +1.5 | +1.3 | +5.1 |
| instrumental | +1.4 | +1.9 | +0.2 |
| end | +1.7 | +1.7 | -0.5 |

The intro is the only section that got quieter (-1.1 dB, instrumental). Everything after it is **+1.5 to +2.7 dB** louder, and the vocal is up **+3 to +5 dB** in the drops, verse 3 and the breakdown, so the vocal sits further forward. The outro/end vocal is unchanged. The overall v5 master is about +2 dB hotter.

## Renderer

Shots reference times symbolically through TimeMap, so `--audio v5 / v5sfx / v5final` (render/src/audio.config.js) loads timing_v5.json + envelopes_v5.json and the cuts follow v5 with no code changes. Remaining literal times in render/src/shots.js: the H1_scrub montage `TR` list (source moments of the video, shifted by up to -0.48 s in v5; cosmetic, can be mapped through time_map) and the evidence-wall pin labels '42.89'/'102.28'/'13.45' (text; v5 values 42.44 / 102.02 / 13.15).

## Intro (see assets/sound/README.md, v5 section)

In v5 the intro impact sits at 6.635 s. It is reduced but still present: sub 20-150 Hz +38.6 dB over the pre-hit level (v4 +42.9), the 3-16 kHz smash +14.4 dB (v4 +14.1; absolute level 6.7 dB lower), and mix RMS over the first second +4.5 dB (v4 +11.0). The final master `assets/sound/Rewind5_final.wav/.mp3` has the impact removed plus the intro SFX.
