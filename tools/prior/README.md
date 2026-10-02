# tools/prior — reusable code copied from the two earlier videos (reference copies, not wired up)

Copied unchanged from `/home/user/jadeqwang/rare-earth-techno-remix` (RE) and `/home/user/jadeqwang/orbital-sunrise-video` (OS).
Paths inside these files still point at their old layout (`/tmp/work/...`, `../audio/...`); adapt them when you adopt one. See `docs/PRIOR_ART.md`.

## rare_earth/render (three.js WebGL2 + Canvas2D, Playwright, SwiftShader)
- `tools/render.mjs`: frame capture: Playwright + SwiftShader flags, one browser per job, `--resume`, `--stills`, ffmpeg mux with an audio slice.
- `tools/serve.mjs`: static server, plus `/work/*` mapped to the big scratch dir (guide frames outside the repo).
- `tools/shots.mjs`: dumps the shot table as JSON, for re-rendering only the changed shots. `tools/profile.mjs`: per-shot render/screenshot ms.
- `tools/encode_release.sh`: two-pass H.264 High ~5.5 Mbit/s, under 100 MB; copies the audio if it is already AAC.
- `src/engine.js`: **best piece.** Render targets, fullscreen shader/pass helpers, dual-filter bloom, and the final compositor (CA, misregistration,
  per-shot static grain, paper stock, scanlines, impact-frame invert, flashes, vignette, shake, zoom punch). `GLSL_LIB` has hash, fbm, halftone and Bayer.
- `src/c2d.js`: Canvas2D scene → texture → render target (optional halftone re-screen). `font()` helper.
- `src/util.js`: easings (cubic, expo, back, elastic, smoother), hash/rng/noise1, ink palette helpers.
- `src/audio.js`: `AudioMap` over `audio.json`: beat/bar phase, kick/snare envelopes, interpolated features, word/line times, snap.
- `src/type.js`: FontFace loading + kinetic type modes: stack, subtitle (karaoke), line, keyword, terminal, decode, hud, censor.
- `src/roto.js`: guide-texture LRU, `frameIndex` (twos, 1e-3 rounding fix), roto shader (print / light / data modes, line boil).
- `src/main.js`: boot + serialised `renderAt(t)`, post merge (shot look × global rhythm), `?play=1` live preview.
- `src/timeline.js`, `src/selects.js`: example edit (shots on word onsets and beats) and per-take lip-sync lag table. Reference only.
- `index.html`, `package.json`: importmap for three; deps `three`, `playwright-core`, `esbuild`.

## rare_earth/pipeline (python)
- `audio_map.py`: beat grid (librosa, polynomial fit), kick/snare onsets, per-frame features → `audio.json`.
- `lyrics_align.py`: Whisper words aligned to the canonical lyrics (difflib), snapped to vocal onsets, monotonic ≥ 70 ms.
- `roto_extract.py`: per-frame guide PNG (R = XDoG line, G = tone, B = green matte with despill) + colour JPEG + meta.json. `extract_selects.py`: runs it for the selected takes.
- `sync/`: lip-sync verification + fixing: `mouth.py`, `mouth_color.py` (two openness metrics), `score.py`, `lag_curve.py` (lag as played),
  `wordstrip.py` (visual check), `remouth.py` (DP mouth transplant), `sync_report.py`, `mouthline.py`.
- `dot_sheet_v1.txt`, `dot_sheet_v3_hair.txt`, `style_sheet_v1.txt`: character-sheet / style-board prompts that worked.

## orbital/video (pure Canvas2D, puppeteer-core, toDataURL)
- `render.mjs`: **best harness.** Built-in localhost server; worker pages pull a queue of missing frames; atomic writes; crash → reopen page + retry;
  modes `--list`, `--sheet` (in-page contact sheet with ms/frame), `--stills`, `--clip`, `--frames --workers`, `--encode`, `--source` (making-of).
  Port it to playwright-core (same API shape).
- `studio.html`: `@font-face font-display:block` + script order; interactive scrubber page.
- `src/core.js`: math/easing/`kf()` keyframes, hash/mulberry32/fbm, beat helpers (`beatPos`, `pulse`), pooled layers, paper tooth + baked paper, `drawClock`.
- `src/main.js`: on-twos clock restarting per shot, `renderAt`, `renderSheet`, `renderSource`, font preloading before `window.ready`.
- `src/timeline.js`: the minimal shot registry. `src/type.js`: lyric helpers (lineAt, wordIn) and the font roles.
- `src/pencil.js`: batched Path2D stroke engine + `analyzePlate` (tone, colour, structure-tensor flow, edges) → hatch/contour fields.
- `src/plates.js`: LRU plate-frame and matte loading → analysis fields.
- `package.json`: puppeteer-core.

## orbital/tools (python)
- `mouth_track.py`: **procedural mouth-open track from the vocal stem** (attack/release, 40 ms lead, b/m/p closures) → mouth.json.
- `lipsync.py`: plate mouth curve (MediaPipe) vs vocal envelope → lag + plot.
- `plate_meta.py`: per-frame face landmarks, sun blob, luminance. `plate_masks.py`: rembg isnet mattes. `extract_plates.py`: takes → frames + index.json.
- `review_sheets.py`: contact sheets of rendered frames labelled with time and shot. `encode_release.sh`: two-pass HEVC 1080p + H.264 720p.
- `extend_ending.py`: spectral-freeze tail extension (NOT for REWIND: the song must stay untouched; reference only).
- `plate_specs.py`: Seedance prompt patterns (LOOK suffix, "exactly as in the reference images", singer plates with audio refs).
- `../timing.example.json`: example timing schema {bpm, beat, t0, beats[], sections[[name,t0,t1]], lines[{sec,text,t0,t1,words[[t,w]]}]}.
