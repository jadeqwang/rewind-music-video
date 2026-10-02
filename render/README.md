# REWIND renderer

Deterministic JS renderer for the REWIND video: Canvas2D scene and type layers, then a WebGL2 post compositor,
captured headless with playwright-core (Chromium under SwiftShader), then ffmpeg.
`window.renderAt(t)` is a pure function of song time `t` (frame / 30, 1920×1080). Nothing calls `Math.random`/`Date`.
Randomness comes from `hash()`/`rng()` in `src/core.js`. Line boil runs on twos (15 drawings/s), and its seed restarts at every cut.

## Layout
```
index.html            page (headless: ?render&shots=lookdev&w=&h= ; interactive scrubber without ?render)
render.mjs            capture harness (see CLI)
src/core.js           math/easing, hash/rng/noise, palette PAL (REDACTED NOCTURNE), pooled canvases, timecode
src/timing.js         TimeMap over ../analysis/timing.json + envelopes.json (falls back to data/*.stub.json)
src/post.js           WebGL2 compositor (raw GL, port of tools/prior rare_earth engine.js): dual-filter bloom, CA,
                      misregistration, static per-shot grain, scanlines, tape warble + tracking band, ripple, zoom/roll/
                      shake, two-tone impact invert, ±flash, rewind grades (cyanGrade positive, neg true negative), vignette
src/engine.js         boot, shotAt, drawShot, renderAt/renderTimed/renderSheet, rewindOf(), miss-driven roto loading
src/roto.js           roto loader (LRU, prefetch) + figure components: contours(), jade(), suits(), star()
src/type.js           fonts + kinetic type: page() (a), slam() (b), subtitle() (c), redact()/redactedLine() (d), revisions() (e)
src/hud.js            evalBar, attempt, annotation (?! ?? !!), foiaBanner, rewindHud (◀◀ ×N, timecode), buildTree/searchTree, cross
src/fx.js             sirens (alternating red/blue floods on the beat), sodiumSweep/Wash, bullet, rain, fillInk
src/scenes/*.js       page, suits, freeze, rewind, slam, tree, road, black (+ index.js registry)
src/shots.js          main edit (PLACEHOLDER: whole song with look-dev assets, every cut symbolic)
src/shots.lookdev.js  12 s look-dev (song 36–48 s)
fonts/                CMU Serif (Computer Modern), Anton, Big Shoulders Display, Archivo (wdth VF), JetBrains Mono + OFL texts
tools/make_stub.py    stub timing/envelopes (from whisper + a 124 BPM grid); superseded by analysis/timing.json
tools/make_lookdev_roto.py  look-dev roto sequences (DoG lines + GrabCut matte on assets/tests images; procedural Jade)
lookdev/              lookdev.mp4, lookdev_sheet.png, sheet_v0..v3 (iteration history), stills
frames/               rendered JPEG frames (gitignored)
```

## Coordinates and orientation
All drawing uses design pixels (1920×1080). The layers are scaled by `S = H/1080`, so `--w 960 --h 540` makes previews.
Canvases are uploaded with `UNPACK_FLIP_Y`, so in GL `uv (0,0)` is bottom-left. Any effect defined in screen pixels
uses `sy = (1-uv.y)*H/S`, which is top-down like the canvas. Every shader result passes through `safe()` (NaN/Inf → 0),
and JS values that reach canvas or GL go through `fin()`.

## Shots and scenes
`buildShots(T)` returns `{id, t0, t1, scene, params}`. Cut times come from the TimeMap, not typed seconds:
`T.word('defense').start`, `T.word('stop', 2, {after: t})`, `T.line(i)`, `T.lineWords(i)`, `T.beat(n)`, `T.downbeat(n)`,
`T.beatIndex(t)`, `T.snap(t)`, `T.section('drop1').start`, `T.event('drop', n)`. Use `T.opt(fn, fallback)` when the data
might lack a reference. A missing word throws on purpose, so a cut never silently lands at 0.
Envelopes: `T.e('vocal'|'rms'|'low'|'mid'|'high'|'onset', t)`, `T.kick(t)`, `T.pulse(t)`, `T.beatPhase(t)`.

A scene module exports `draw(ctx, localT, globalT, shot, data)`, which may be async.
- `ctx = {g, ty, post, boil, seed, rewinding, mode, shot, S}`. `g` is the scene layer (it gets bloom, CA and the rewind grade) and `ty` is
  the type/HUD layer (composited after the grade, with smaller CA). The scene sets the shot's look on `post`, using the uniform names from `post.js`.
  `seed` is the boil seed (hash of shot id and drawing index). `rewinding` is true when the scene is re-rendered inside a rewind; scenes then
  skip their HUD and draw past selves as ghosts. `mode: 'print'` gives a bone-stock "file photo" (used by freeze).
- `data = {T, roto, shots, SCENES, shotById, shotAt, drawShot, rewindOf}`.
- Export `noRewind = true` to keep a scene from being re-rendered inside a rewind.

To add a scene, write `src/scenes/foo.js`, register it in `scenes/index.js`, then reference `scene: 'foo'` in a shot table.

### The rewind
`rewindOf(ctx, shotId|null, fromT, toT, progress, {echo, echoDt, echoAlpha})` re-renders earlier shots at
`ts = fromT + (toT-fromT)*progress`, with motion-echo ghosts at later source times. Passing `null` picks the shot that covers each time,
so one rewind can cross several shots (the look-dev rewinds suits → page). This works because every frame is a pure function of t.
`scenes/rewind.js` adds the stepped ×2/×4/×8 schedule, the cyan grade, a 2-frame true negative at the start and at each speed change,
ripple, warble, tracking band, scanlines, the backwards timecode and a scrub rail.

### Roto
`assets/roto/<id>/{lines,matte,face,features,hair}/NNNN.png` (white on transparent, alpha = signal) and
`meta.json {fps, frames, w, h, layers, per_frame:[{glints, faces, mouth, tilt}]}`. A shot lists its sequences in `params.roto`
(they are preloaded at boot).
`roto.get()` returns a cached bitmap, or records a miss. `renderFrame` loads the misses and redraws, so output never depends on cache state.
After each frame the current shot is prefetched for about 10 frames ahead and 2 behind. An LRU keeps up to 160 bitmaps.
- `contours()`: luminous lines (tint, additive, affine boil jitter, optional double stroke, depth fog, matte exclusion).
- `jade()`: flat bone fill, hair as ink, interior lines outside the face mask only. Inside the face mask only `features`
  (eyes at full size, brows, nose tip, hair/jaw contours) and a mouth driven by `T.e('vocal')` are drawn, with no skin texture
  (docs/LIKENESS_RULES.md). `ghost: true` gives the outline-only past self, `rim` gives an edge light, `light` gives a sodium/siren wash.
- `suits()`: black cut-out, one-sided siren rim, FOIA face bars wider than the head plus a `(b)(6)` label, sunglasses glint stars.

## CLI
```
node render.mjs --list [--shots lookdev]
node render.mjs --sheet 36,37.5,40:48:0.5 [--cols 4 --tw 480] [--out lookdev/sheet.png] [--shots lookdev]
node render.mjs --stills 38.8,44.6 [--out dir]
node render.mjs --range 36 48 [--workers 3] [--force] [--dir frames/x]   # resumable, tmp+rename, one browser per worker
node render.mjs --range 36 48 --encode --out lookdev/lookdev.mp4           # or --encode alone on an existing frame set
  common: --shots main|lookdev  --w 1920 --h 1080  --q 0.94  --crf 17  --verbose  --flags "<extra chrome flags>"
```
Chromium is found automatically under `/opt/pw-browsers/chromium-*/chrome-linux/chrome`. It runs with the SwiftShader flags plus
`--disable-accelerated-2d-canvas`: CPU Canvas2D is about 2× faster than SwiftShader-backed 2D. A built-in static server serves the
repo root. Encoding uses libx264 at CRF 17, yuv420p, AAC 256k, `-ss/-t` on "Rewind (4).mp3", `-shortest` and `+faststart`.

Performance at 1080p: about 0.75–0.8 s per frame per worker in-page (render + GL + JPEG). With 3 workers that is about 0.28 s per frame
effective, so the full song (6,974 frames) takes about 33 minutes. Rewind frames cost the most (4 re-renders), about 1.2 s each.
Output is deterministic: the same frame from different processes and in a different order is byte-identical.
