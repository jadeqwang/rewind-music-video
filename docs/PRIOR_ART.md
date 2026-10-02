# PRIOR ART — what the two "good" videos did, and what REWIND should reuse / avoid

Sources (read-only clones):
- **RE** = `/home/user/jadeqwang/rare-earth-techno-remix` — "Rare Earth", 2:09, 1080p24, H.264 5.5 Mbit/s. Riso-print anime ("SIGNAL PRINT").
- **OS** = `/home/user/jadeqwang/orbital-sunrise-video` — "Orbital Sunrise", 4:02, 1080p24, HEVC 2.9 Mbit/s. Colored-pencil rotoscope.

Both were made in this same kind of container: Seedance 2.5 on Cloudflare, a JS renderer in headless Chromium, ffmpeg.
The key docs are `RE/docs/PROCESS.md` (very detailed, read it), `RE/docs/reviews/gemini_preview3.md`, `RE/docs/TREATMENT.md`,
`OS/README.md`, `OS/docs/STYLE_BIBLE.md`, `OS/docs/TREATMENT.md` and `OS/docs/SHOTLIST.md`.
Copies of the reusable code are in `tools/prior/` (see `tools/prior/README.md`).

---

## 1. Render pipeline

### Shared architecture (both projects, and it worked)
```
song ─► stems (UVR MDX-Net Kim_Vocal_2 via audio-separator) ─► Whisper (Workers AI) word times
     ─► align to canonical lyrics (difflib) + snap to vocal onsets ─► beat grid + kick/snare onsets + per-frame features
     ─► ONE JSON timing file the renderer loads (RE render/data/audio.json, OS video/data/timing.json)
design sheets (GPT Image 2.5 / Nano Banana Pro) ─► Seedance 2.5 plates (sheet as image ref, song slice as audio ref)
     ─► python analysis to guide maps (never displayed) ─► JS renderAt(t) ─► headless Chromium ─► JPEG frames ─► ffmpeg
```
- **Determinism contract:** every frame is a pure function of song time `t` (`window.renderAt(t)`). No state carries from frame to frame
  (caches are fine as long as results don't depend on them). That allows parallel workers, any-order and resumable rendering, and
  re-rendering single shots. Randomness is hash-based (`hash(n)`, mulberry32 `rng(seed)`, value-noise/fbm), seeded by shot or drawing index.
- **Shot table / edit:** `SHOTS[] = {id/name, t0, t1, scene/fn, type(), look/post}`; `shotAt(t)` picks the last shot covering t;
  shot-local time `lt = t - t0`. Cuts are placed on word onsets `A.W(line, word)` and beats `A.B(i)` / `beatTime(n)`, never on hand-typed seconds.
  (RE `render/src/timeline.js` = the whole edit, 440 lines; OS `video/src/timeline.js` + `shots.js`/`shots2.js`.)
- **"Drawn on twos":** characters (RE), or everything (OS), update 12 drawings/s, with a clock that restarts at each cut so cuts stay frame-exact
  (OS `main.js`: `t = sh.t0 + floor((t - sh.t0)*12)/12`). Camera, type and FX stay on ones in RE. Panic/impact shots use ones.
  **For REWIND at 30 fps:** use 15 drawings/s (twos) or 10/s (threes). 24-based lags don't map directly.
- **Studio/scrubber page:** the same HTML page runs interactively (scrub slider, `?play=1` with audio) and headless (`?render`). Very useful for review.

### RE: three.js WebGL2 + Canvas2D, Playwright, SwiftShader
- `render/index.html` (importmap for three) → `src/main.js` (boot, `renderAt`, serialises calls through a promise chain) →
  `src/engine.js`: WebGL renderer, HalfFloat render targets, fullscreen `shader()`/`pass()`/`passOver()` helpers, a 5-level
  **dual-filter bloom**, and a **final compositor shader**: chromatic aberration, plate misregistration, bloom, type-layer mix,
  paper stock (baked fbm fibres), **per-shot static grain** (2-px cells), scanlines, two-tone impact-frame inversion, ± flashes,
  vignette, shake, zoom punch and roll, fade. `GLSL_LIB` has hash, vnoise, fbm, rot, **AM halftone**, line screen, overprint and Bayer 4×4 dither.
- `src/c2d.js`: draw a scene in Canvas2D (design px 1920×1080), upload it as a texture, optionally re-screen it in halftone.
- `src/type.js`: FontFace loader + kinetic modes: `stack` (word slams on the syllable, easeOutBack, plate offset), `subtitle`
  (karaoke clip-fill by word timing), `line` (whole line on screen, the sung word lit in an accent), `keyword` (huge word,
  stretch-in + kick pulse, auto-fit to maxW), `terminal` (typed mono log with cursor), `decode` (glyph → scramble → Latin), `hud`, `censor`.
- `src/audio.js` `AudioMap`: `beat(t)` gives {i, phase, period}, plus `bar(t)`, `kick(t)`/`snare(t)` exponential envelopes, `feat(name,t)`
  (interpolated per-frame features), `W(i,j)`/`L(i)` word and line times, `snap(t)` and `B(i)`.
- `src/roto.js`: LRU texture cache of guide PNGs, `frameIndex(meta, clipTime, twos)` (with the 1e-3 frame-rounding fix),
  and a roto shader with 3 modes: PRINT (halftone shadow ink + flat accent inks by hue class + ink line), LIGHT (neon line + bloom),
  DATA (1-bit dither). Line boil = per-drawing noise displacement of the sampling UV.
- Global rhythm layer (`buildGlobalPost` in timeline.js): kick zoom punch, CA and shake in drops, misregistration on the snare,
  2-frame impact frames on section hits.
- Capture: `render/tools/render.mjs` (Playwright `chromium.launch` with
  `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`, `renderAt` then
  `page.screenshot({type:'jpeg', quality:94})`). **One browser process per job**, because SwiftShader rasterises in the GPU
  process and pages in one browser contend for it. `--resume` skips frames that exist. `tools/shots.mjs` dumps the shot table so
  you can re-render only the changed shots. `tools/serve.mjs` is a static server that also maps `/work/*` to the big guide-frame dir outside the repo.
- Speed: "~1 s per 1080p frame per browser process on CPU", run with 3 jobs. Per-shot profiling is in `tools/profile.mjs`.
- Encode: CRF 17 for working copies; release = **two-pass H.264 High at ~5.5 Mbit/s** (`render/tools/encode_release.sh`) to
  stay under GitHub's 100 MB limit. The audio was copied (`-c:a copy`) on picture-only revisions.

### OS: pure Canvas2D (no WebGL), puppeteer-core, toDataURL
- `video/studio.html` loads plain `<script>`s (globals, no bundler): `core.js` (math, easing, `kf()` keyframes, hash/rng/fbm,
  beat helpers `beatPos/beatN/beatTime/pulse`, palette, pooled full-frame layers, **paper tooth** pattern + `toothIn()` via
  `destination-in`, baked paper with fibres and vignette, `drawClock`), `pencil.js` (batched Path2D stroke engine; `analyzePlate()` reads tone,
  colour, structure-tensor flow and edges; hatch and contour fields), `plates.js` (LRU of plate frames + rembg mattes),
  `type.js`, `shots*.js`, `main.js`.
- Fonts: `@font-face` with `font-display: block`, then `document.fonts.load()` of every face before `window.ready = true`. RE does the same with the `FontFace` API.
- Capture: `video/render.mjs`. It runs its own localhost static server (so `getImageData` on plates doesn't taint the canvas), then
  `window.renderAt(t)` returns `canvas.toDataURL('image/jpeg', .93)`. That is faster than a screenshot and needs no GPU.
  N worker pages pull from a shared queue of missing frames, write files atomically (tmp + rename), and if a page crashes or hangs it
  is reopened and the frame retried once. Modes: `--list`, `--sheet=` (contact sheet rendered in-page with ms/frame per tile),
  `--stills=`, `--clip=a:b` (pipes MJPEG to ffmpeg with the matching audio slice), `--frames=a:b --workers=4` (resumable),
  `--encode`, `--source=` (making-of: the plate as placed next to the drawn frame).
  Launch flags: `--disable-renderer-backgrounding --disable-background-timer-throttling --force-color-profile=srgb
  --js-flags=--max-old-space-size=4096`, `protocolTimeout: 0`.
- Encode: `tools/encode_release.sh` makes a two-pass HEVC 1080p (~94 MB) and a two-pass H.264 720p. Pencil hatching that boils is very
  expensive to compress (2.9 Mbit/s HEVC is visibly soft).

### Recommendation for REWIND
- **Harness:** start from **OS `video/render.mjs`** (queue of missing frames, atomic writes, crash-retry, sheet/stills/clip modes,
  built-in server) and switch it to Playwright (`playwright-core` is already used by RE). If we use WebGL, add RE's SwiftShader flags and
  **one browser per worker**. If we stay with Canvas2D, keep `toDataURL` capture.
- **Engine:** RE `engine.js` (post compositor + bloom + GLSL_LIB) is the best starting point for a stylised 2D-plus-shader look
  (CA, grain, misregistration, impact frames and flashes are exactly what a time-stop / rewind effect needs). `c2d.js` handles
  vector and type scenes.
- **Timing:** RE `pipeline/audio_map.py` + `lyrics_align.py` → `audio.json`, read by RE `audio.js` (`AudioMap`). This song has
  a constant 124 BPM, so a polynomial grid isn't needed, but keep the tracked beat list.
- **Type:** RE `type.js` modes (stack, keyword, line, decode, terminal) and its font loader. OS type rules: one impact face, one
  intimate serif italic, one mono for telemetry.
- **Review:** `--sheet` contact sheets every 0.5 s plus a Gemini watch-through (prompt in `RE/docs/reviews/gemini_preview3.md`).

## 2. How Seedance / gen media was used

- **Never displayed, in both projects.** Plates are reference only: RE extracts XDoG line (R), bilateral tone (G) and a green-screen matte with despill (B)
  into one PNG per frame, plus a smoothed colour JPEG used only for ink classification (`pipeline/roto_extract.py`, ~1.5 GB of guides
  for the film). OS reads plate JPEGs (960×540) in-browser and builds tone, flow and edge fields, plus MediaPipe face landmarks, sun blob,
  luminance (`tools/plate_meta.py`) and rembg isnet mattes at 12 fps (`tools/plate_masks.py`). Procedural layers (sun rays, type,
  telemetry) lock onto plate measurements, e.g. a tracked star position in RE's poster shot.
- **Green-screen plates** (RE) for the light-mode performances composited over procedural backgrounds. Prompt line:
  "a plain, flat, evenly lit solid chroma-key green screen (#00FF00) filling the whole frame". "Context" plates keep the set.
- **Prompting that worked** (OS `tools/plate_specs.py` docstring): "favour traceable pictures: hard directional light, clean
  silhouettes, readable motion, **one clear action per plate**". There is a shared LOOK suffix on every prompt and a character
  descriptor that says "exactly as in the first two reference images", plus "No on-screen text, no captions".
  RE adds `" No text, no subtitles, no logos."` and gives environment plates their **own** style line (appending the character line to
  them by mistake was a bug). Reference images must be between 0.39:1 and 2.5:1, so crop the sheets.
- **Lip sync.** The song slice for exactly the shot's window `[t0, t0+dur]` is passed as the audio reference, with `generate_audio:false` in RE (it avoids
  the output copyright filter; OS used `true` so it could cross-correlate the plate's own audio to see where Seedance placed the song).
  Prompt: "She sings the words of the reference audio with precise, clearly articulated lip sync."
  Seedance sync is **close but not frame-exact**, and it often idles before and after the phrase.
  - RE verification loop (`pipeline/sync/`): track the mouth (anime LBP cascade, plus a second independent colour metric for the mouth interior), take the openness curve,
    cross-correlate it with the vocal-stem envelope **only over the window the edit uses**, **as played (on twos)**, and pick the per-take lag
    (`clipTime = t − start + lag`). Trust a lag only when both metrics peak together. `wordstrip.py` makes face crops at each word onset for an eye check.
    Final fix: `remouth.py` re-times the mouth separately from the body, cel-animation style. For each drawing it picks, by dynamic programming,
    a mouth frame from the same take that matches the vocal target (log-RMS × pYIN voicing), registers it with ECC and feather-blends it.
    Correlation went from about 0.2 to 0.8–0.9 on 219 of 263 drawings.
  - OS: after `lipsync.py` showed Seedance was off, the singer's **lips were redrawn procedurally from the vocal track**
    (`tools/mouth_track.py`: RMS with 20 ms attack and 90 ms release, opened about 40 ms ahead of the sound, forced shut on b/m/p onsets from the word timings)
    at the plate's own MediaPipe lip landmarks, with the plate's mouth painted out. **Since REWIND redraws everything, this is the cheapest robust approach.**
- **Character sheets:** RE's DOT sheet (GPT Image 2.5 was the best for canonical sheets) has 4 full-body views at the same scale, 3 expression heads
  (singing "ah", smile, determined) and prop and detail callouts. The prompt is `tools/prior/rare_earth/pipeline/dot_sheet_v1.txt`.
  OS made separate turnaround and faces sheets for Jade, photoreal in the same grey hoodie, generated from real photos of her (`media/chars/jade_src/`).
  Revisions were done as text-only edits of the canonical sheet (the reference photo was never sent to a model). Nano Banana ignored the hair-edit instruction.
- **Image models invent text and facts.** Seedance invented lettering ("PACE EARTH", "D20 IHz") that had to be tracked and inpainted
  (`plate_fixes/`). Sheet labels had wrong facts and had to be repainted. → Keep text out of every gen prompt; all lettering is ours.
- Cost (RE): about $147 total, Seedance about $142 for 103 runs and 478 s of 720p. Jobs are async through a relay Worker that mirrors to KV (the provider
  media host and `*.workers.dev` are blocked; synchronous calls get cut off at about 30 s). Use a **file lock on the manifest**, because parallel collectors raced and lost takes.

### Lessons quoted from the docs
- "Whole-clip scores were misleading, because Seedance often idles before and after the reference phrase." (RE PROCESS §3)
- "Lags tuned on single frames turned out to cost real sync once held [on twos]" ("of a star" 0.45 as played vs 0.70 on ones). (§3 pass 2)
- "A lag stored as −0.291667 had landed one frame away from −7/24" → tolerate 1e-3 of a frame in the frame lookup.
- One lag per take "fits one stretch of a shot and misses the next"; the mouth has to be timed separately from the body. (§3d)
- Review feedback (Gemini, preview 3): hook 6/10, **lyric legibility 5/10, lip sync 4/10**, polish 6/10. Its points: type collides with hands and the eye line, text next to the
  crying face dilutes the beat, low-contrast yellow HUD over halftone is illegible, a full-white flash "feels unmotivated" (use a stepped
  4-frame exposure taper), **line boil strobing under bloom** (they halved the boil).
- Earlier previews: "lyrics still sat on DOT's face in eight shots" → frame each shot so the words sit in the calm third.
  "The cold open was not a strong enough hook" → an animated poster frame in the first 2–3 s. "The first frame was black." NaN black
  blobs came from geometry without normals. Keywords overflowed the frame → auto-fit type to maxW.
- Viewer note: "the other world kept showing the same shots" → rule: **no plate plays twice**.
- User/songwriter asks: change the hairstyle (cost a full re-shoot of 18 shots and 56 takes), set the correct lettering, fix lip-sync drift, keep the
  hard-to-hear line ("launch **or** self-destruct") whole on screen, fact-check everything people might screenshot, credit the songwriters.
- Encoding: per-frame grain cost about 16 % more bits "for nothing visible", so grain is seeded per shot and static within it.
  The kick zoom punch is limited to the drops.
- OS: "the hatch layout shimmers but does not strobe" (±12 % nudge per drawing); the paper tooth never moves; big words get a "knockout" clearing in the drawing.
- Two coordinate conventions (y-down canvas vs y-up shader) "caused several early bugs (moon at the top, flipped textures, type upside-down)".

## 3. Visual style

Contact sheets were viewed: 12 stills from each final MP4, plus full-res crops.

**RE (Rare Earth) — riso anime.** Klein-blue halftone, orange spot ink, wide extended grotesk (Archivo 900 expanded) lyric slams with
an orange offset plate, neon mint-line "light mode" on black, a pink/magenta other world, a brutalist Win95 funding window, a mint
constellation finale.
- Strong: a coherent spot-ink system; the halftone character redraw is clean and reads as real anime print; type is bold and on the syllable; the shifts between
  print, light and data modes give the film an arc; the procedural science inserts (Drake equation, waterfall, contact graph) are good.
- Weak: blue saturation fatigue (most of the film is one hue); the roto still looks like filtered footage in places; lyric/face collisions
  needed three passes; the neon mode boils and strobes; the type language is "big word centre screen" over and over. Lip sync was the lowest score.

**OS (Orbital Sunrise) — coloured pencil.** White-line etching hatching on black paper, radial orange/gold sun-ray strokes, Anton
cream caps with red Cyrillic (Oswald), Instrument Serif italic for the singer, a warm-white paper section for Earth, then a title card on black.
- Strong: a concept that justifies the medium; a restrained palette ("pencil box"); the type hierarchy (impact / intimate / telemetry);
  type set along a curve around the helmet; hero sunburst frames; the black→white paper switch at the landing.
- Weak: the white-paper sections are **grey and muddy** (dense hatching over photoreal faces is unflattering and low contrast; the singer's face
  reads as noise in the crop at 2:30); the serif subtitles get lost on the pale paper; the long sections are low-energy and slow; at 2.9 Mbit/s HEVC
  the hatching smears into a soft texture; much of the frame is mid-grey texture with no focal value.

**So REWIND should be distinct and better:**
- Not riso-blue halftone, and not pencil hatching. Night driving on Lake Shore Drive suggests a high-contrast **2–3 ink night palette**
  (sodium orange, siren red/blue, black) with big flat shadow shapes (graphic-novel or noir), not texture everywhere.
- Keep focal values clean: large flat areas compress well and read on a phone. Avoid full-frame fine texture that boils.
- Make the **rewind itself the signature device** (Braid-style: time reverses with frame-history trails, desaturation, CA,
  scanline smear, a reversed type crawl). RE's post compositor already has CA, misregistration, invert and flash hooks.
- Type should have more than one compositional idea: lyrics on road signs and lane markings, in the rear-view mirror, as a chess/search-tree
  overlay (move notation, branch counters "LINE 1: ✕", "LINE 3: ✓"). Keep it off faces from the start (calm-third framing rule).
- A faces policy: stylised faces with drawn mouths keyed to the vocal (OS approach), not photoreal hatching.

## 4. Gotchas

- **Chromium path:** `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (both projects hard-code it; there is also `chromium_headless_shell-1194`). Don't run `playwright install`.
- **WebGL headless = SwiftShader** (CPU). Flags: `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`.
  Use one browser process per parallel job (shared GPU process contention). Use `preserveDrawingBuffer: true` if you screenshot.
  Guard shaders against NaN/Inf (RE's bloom does `if(any(isnan(c)))`), because they showed up as black blobs.
- **Canvas2D path** needs no GPU: `toDataURL` from the page, served over localhost so `getImageData` on images isn't tainted.
  `--js-flags=--max-old-space-size=4096` and `protocolTimeout: 0` are needed for long renders. LRU-cap the image and analysis caches (OS: 24 images, 16 analyses; RE: 90 textures, evict 30).
- **Machine:** this container has 4 cores and 15 GB RAM. RE ran 3 jobs at about 1 s/frame each. REWIND is 232.44 s × 30 fps = **6,974 frames**,
  so at about 0.35 s effective per frame that is about 40 min per full pass, more with heavy scenes. Render previews at 960×540, and full res only for changed shots.
- **Throttling:** `--disable-renderer-backgrounding --disable-background-timer-throttling`. Serialise `renderAt` calls (RE's promise chain) so
  overlapping evaluations don't interleave.
- **Fonts:** load every face (FontFace API or `@font-face font-display:block` plus `document.fonts.load(...)`) **before** signalling ready,
  or the first frames render in a fallback font. `ctx.fontStretch` and `letterSpacing` need try/catch on older canvases. Ship OFL licence texts.
  RE subset Noto Sans SC to only the glyphs used.
- **Colour:** `--force-color-profile=srgb`. In three.js set `outputColorSpace = LinearSRGBColorSpace` and textures to `NoColorSpace` when authoring
  colours directly; `flipY` mistakes flip textures and type.
- **Frame rounding:** use `Math.floor(t*fps + 1e-3)` (or 1e-6) in every frame lookup. Restart the drawing clock per shot.
- **Audio sync check:** the final MP4's audio, the source MP3 and the stem cross-correlated at exactly 0 ms (RE). Use `-ss/-t` on the audio input
  for clips, and `-shortest`. **Do not normalise or alter the song** (RE's sound design mixed SFX only into quiet gaps and peaked at −4.4 dBFS; we may add none).
- **Proxy/hosts:** blocked: `*.workers.dev`, developers.cloudflare.com (they read the docs from a sparse clone of cloudflare/cloudflare-docs), Hugging Face,
  fbaipublicfiles, download.pytorch.org (so Demucs failed; the UVR models came from GitHub releases). BS-Roformer was too slow on CPU (about 71 s per chunk).
  MediaPipe and rembg models were placed under `/tmp/work/models`.
- **Repo size:** frames, guides (~1.5 GB) and takes live outside git (`/tmp/work` there; for us `analysis/ assets/ render/`). The release MP4 must be < 100 MB
  (two-pass encode). Static, per-shot grain and limited punch zooms keep the bitrate down.
