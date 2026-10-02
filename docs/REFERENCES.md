# REWIND — research references (rendering, rotoscope, visual language, attention)

Compiled 2026-10-02. Benchmarks marked [MEASURED] were run in this container (4 vCPU, 15 GB RAM, no GPU,
Playwright Chromium 141.0.7390.37 at /opt/pw-browsers/chromium-1194). Everything else is from the linked sources or is
labelled as an estimate.

---------------------------------------------------------------------------------------------------------------------
## 1. The user's reference: "github.com/JohnHeibel/PDo" = **JohnHeibel/PDoomVideo**

- Repo: https://github.com/JohnHeibel/PDoomVideo — "Source code for the Claude Opus 5.5 music video for *I'm Upping My
  P(doom)*" (video: https://youtu.be/8j-hR4fJywU). Follow-up kit: https://github.com/JohnHeibel/ClaudeAnimationBase
  ("p5.js + p5.brush, the Clawd character, 31 acted emotions and a guide for the model"). Both cloned read-only to
  /home/user/johnheibel/{pdoomvideo,ClaudeAnimationBase} for reference.
- Context: part of the "Claude-Pop" wave (Sept 2026) after Opus 5.5's launch — deckard/@slimer48484 "Claude-Pop - I'm
  Upping My P(Doom)", makevoid's paper-cutout remake (Opus 5.5 + ~$65 of image/video gen), mexicat's version (TypeScript +
  three.js/WebGL deterministic renderer), Nate Sharpe's "Let's Lower the P(doom)!", A.J.'s pop-punk single where "everything
  you see and hear is generated from javascript". Our video lands in this exact discourse; the "code paints every pixel"
  claim is itself a hook. Sources: https://x.com/makevoid/status/2103945695803924943 ,
  https://x.com/ivanopcode/status/2104586605621133806 , https://x.com/aj_dev_smith/status/2102575577563570450 ,
  https://www.radneurons.com/claude-opus-5-5-now-makes-music-videos/
- **How it renders** (read from source):
  - `studio.html` loads p5.js 2.x + p5.brush 2.x; p5 canvas is `createCanvas(1920,1080,WEBGL)`, `noLoop()`. A separate
    visible 2D `<canvas id=out>` is the compositor: WebGL paint layer -> `drawImage` -> letters layer -> paper grain
    multiplied -> karaoke text. Fonts awaited via `document.fonts.load` before `window.ready = true`.
  - Page exposes `window.renderAt(t, mime, q)`: sets global `T`, `await redraw()`, composites, returns
    `outC.toDataURL('image/jpeg', .94)`. Node (`render.mjs`, puppeteer-core) calls it via `page.evaluate`, base64-decodes,
    writes `out/frames/f%05d.jpg` atomically (write .tmp then rename) -> resumable.
  - **Determinism contract** (ANIMATION_GUIDE.md): every shot is a pure function `fn(t, lt, dur)`; no `Math.random()`;
    `randomSeed(1000 + floor(T*BOIL)); noiseSeed(77)` per frame, so `jit()` jitter re-seeds 12x/s -> deliberate
    hand-drawn "line boil" (on-twos/threes feel) yet byte-reproducible. `hash(i)` for stable per-object randomness.
  - Parallelism: N pages in one browser (`--workers=4`), each pulling the next missing frame index — frames render out of
    order, which is why purity matters.
  - Encode: `ffmpeg -framerate 24 -i f%05d.jpg -i song.mp3 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac
    -shortest`. Also a streaming mode (`image2pipe` mjpeg into ffmpeg stdin) for short clips.
  - Review loop: `--sheet=t1,t2,...` renders a contact sheet JPEG (prints ms/frame) that the model opens with Read — the
    key to agentic iteration. Budget in guide: <=2.5 s/frame (GPU), "hundreds of fills fine, thousands not".
  - Structure: `chapter(name,start,end,[[t0,shotFn],...])` registry, `WIPES` brush transitions at chapter times,
    beat helpers `bpOf/beatN/pulse/seg/kf`, camera `camBegin/camEnd`, `shakeXY`, `iris`, `flash`.
  - Headless Linux (ClaudeAnimationBase/render.mjs): `--no-sandbox`; `--soft-gl` => `--use-angle=swiftshader
    --enable-unsafe-swiftshader`; NVIDIA: `--use-angle=gl-egl` or `vulkan`; `gpu_probe.mjs` prints the renderer string.
    README: soft-gl is "slow on watercolour fills, but it works". Issue #7 (a 6-min MV made with the kit) asks for
    supersampling (1-px lines vary 13-36% darkness with grid alignment), a Python music toolkit (tempo map / lyric
    alignment — they had up to 0.68 s drift), IK for limbs: https://github.com/JohnHeibel/ClaudeAnimationBase/issues/7
- **Steal**: the `renderAt(t)` contract, contact-sheet review, resumable atomic frame files, seeded boil, chapter/shot
  registry. **Don't copy**: p5.brush watercolor (thousands of WebGL fills; too slow on SwiftShader, wrong mood).

---------------------------------------------------------------------------------------------------------------------
## 2. Deterministic browser video rendering (2026) — options and recommendation

| Tool | What it is | Verdict for us |
|---|---|---|
| Remotion (https://www.remotion.dev) | React; renders each frame in headless Chrome via `renderMedia`, `<OffthreadVideo>` for exact video frames, `useCurrentFrame()` | Most mature, but React overhead, license: free only for individuals / <=3-employee cos ($25/seat/mo "Creators" otherwise; https://www.remotion.dev/docs/license/pricing). Fine but overkill. |
| Motion Canvas (https://motioncanvas.io) | Generator-based TS animation, editor UI, render from browser | Great for diagrammatic tweening; rendering is editor-driven, not headless-first. |
| Revideo (https://github.com/redotvideo/revideo) | Motion Canvas fork + headless render + audio | MIT, but team moved to Midrender; newest engine work "not upstreamed" (https://midrender.com/revideo). Risky dependency. |
| Theatre.js (https://www.theatrejs.com) | Keyframe sequencer/studio UI for JS values | Useful only as a keyframe editor; still need our own capture. Project activity slowed. |
| timesnap/timecut | Virtual-time overriding of rAF/Date in puppeteer | Only needed for code that runs on wall-clock; we control time explicitly, so unnecessary. |
| **Raw Canvas2D/WebGL2 + Playwright + ffmpeg** | Our own `renderAt(frame)` | **Recommended.** Zero framework, fully deterministic, matches PDoomVideo pattern and BRIEF. |

**SwiftShader viability [MEASURED]** — launch args `--use-angle=swiftshader --enable-unsafe-swiftshader
--ignore-gpu-blocklist`; renderer string: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)))`. WebGL2 works.
- full-screen 1080p WebGL2 fragment shader, 5-octave fbm + threshold: **~30 ms/frame** (draw + `gl.finish`)
- WebGL shader + `toDataURL('image/jpeg',.92)`: ~200 ms/frame (readback+encode dominates)
- Canvas2D: 3000 stroked lines + 160px text: ~50-100 ms draw; +JPEG toDataURL ~180 ms; `page.screenshot` jpeg ~113 ms
- => at ~0.25-0.4 s/frame with 3 parallel pages on 4 cores, 6974 frames (232.44 s x 30) ≈ 10-20 min. **Viable.**
- Caveats: Chrome M139+ refuses SwiftShader WebGL unless `--enable-unsafe-swiftshader` is passed
  (https://issues.chromium.org/issues/40277080 , https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md).
  A WebGL2 shader-link regression under SwiftShader was reported for Chrome 153 (issuetracker 562608145) — **pin the
  Playwright Chromium 141 we have**; never auto-update. Keep shaders simple (no huge loops / dynamic indexing).
  p5.brush-style "thousands of draw calls" is the slow path on SwiftShader; few full-screen passes are the fast path.

**Recommended pipeline (concrete)**
1. Python pre-pass (offline, cached): beat grid (124 BPM; beat = 0.4839 s), section markers, onset/kick/snare envelopes
   from stems (analysis/stems), forced-aligned lyric word timings -> `render/timeline.json`. Rotoscope layers
   (edges, masks, depth, flow) from Seedance clips -> per-shot PNG/WebP sequences or packed atlases at the needed res
   (often 960x540 is enough for line art, upscaled in shader = free "grain").
2. Single `render/index.html` with ES modules, all assets local (no network), fonts loaded + `document.fonts.ready`,
   then `window.ready=true`. Expose `window.renderFrame(n)` -> `t = n/30`; every layer is a pure function of `t`.
   Seeded PRNG (mulberry32 / hash(t-quantized)) only; boil = reseed every 2-3 frames.
3. Composition: one WebGL2 canvas for full-frame passes (dither/halftone/feedback/chromatic split, using roto textures),
   one Canvas2D overlay for type/UI (crisp text), composited into an output 2D canvas. Image loading: preload a shot's
   frame sequence via `createImageBitmap` before its first frame; await decode inside `renderFrame`.
4. Playwright (Node) driver: `chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
   args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--disable-background-timer-throttling','--disable-renderer-backgrounding']})`,
   viewport 1920x1080 deviceScaleFactor 1, 3 pages, each pulls next missing frame, writes `render/frames/f%05d.jpg`
   (q .95) or PNG for chunks with fine dither (JPEG ruins 1-px dither — use PNG or encode via pipe).
5. Stills/contact-sheet mode (`--sheet=t1,t2,...`) for review; `--range=a:b` for partial re-renders.
6. Encode: `ffmpeg -framerate 30 -i render/frames/f%05d.png -i "Rewind (4).mp3" -map 0:v -map 1:a -c:v libx264
   -preset slow -crf 16 -pix_fmt yuv420p [-tune grain if grainy] -c:a aac -b:a 320k -movflags +faststart
   -shortest out.mp4`. For X upload keep <=512 MB, H.264 High, AAC, 1080p30.
   Dither/halftone note: add a tiny grain or render dither at 2x pixel size; pure 1-px checker dither turns to mush
   under H.264 + X re-encode. Test an X-reencoded copy.

---------------------------------------------------------------------------------------------------------------------
## 3. Rotoscope / "draw over live action" in code

**Precedents**
- *A Scanner Darkly* (2006, Bob Sabiston's Rotoshop): artists drew vector shapes on keyframes; software interpolates —
  smooth gliding shapes, flat color regions, the "scramble suit" (identity cycling every few frames = perfect for the
  faceless agents). Also *Waking Life*, Amazon's *Undone* (2019, rotoscope over painted backgrounds).
- a-ha "Take On Me" (1985, Steve Barron; animators Michael Patterson & Candace Reckinger, ~3000 pencil frames): sketchy
  pencil line boil, reality<->sketch threshold crossing, the hand reaching out of the comic, final escape by bashing
  through. Directly maps to "shot -> world turns to line art -> rewind".
- *Loving Vincent* (2017): 65,000 oil-painted frames over live action; brush strokes that move with the scene.
  Code analogue: Litwinowicz 1997 "Processing Images and Video for an Impressionist Effect" — strokes oriented along
  gradients, advected by optical flow, added/removed where density changes.
- *Spider-Verse* (2018/2023): animating on twos for characters vs ones for camera; Ben-Day dots / halftone shading;
  CMYK misregistration (chromatic offset) for out-of-focus instead of blur; hand-drawn ink lines over 3D; per-character
  frame rates & styles; comic caption boxes / onomatopoeia. *Puss in Boots: The Last Wish* (2022): painterly frames,
  and the panic-attack scene where frame rate, color and sound collapse — a model for "performance anxiety".
- Rotoscope MVs: Kanye "Heartless" (Hype Williams), Linkin Park "Breaking the Habit", Gorillaz-style hybrid.

**Techniques and CPU cost (for ~7000 frames). [MEASURED] = OpenCV 4 here at 1920x1080 unless noted**
| Look | Method | CPU cost |
|---|---|---|
| Hard edges | Canny | **5 ms** [MEASURED] |
| Ink / woodcut / Scanner-Darkly line | XDoG (Winnemöller 2012: DoG with sharpen p, soft threshold tanh) + optional flow-based smoothing (FDoG) | **45 ms** numpy [MEASURED]; FDoG ~10x |
| Clean "artist" line art | TEED (58K params, https://github.com/xavysp/TEED), PiDiNet, ControlNet annotators "lineart"/"informative drawings" (Chan et al. CVPR'22), DexiNed; HED via cv2.dnn (heavier) | TEED est. ~50-150 ms @ 540p; HED ~0.5-1 s |
| Motion vectors | DIS optical flow (cv2 `DISOpticalFlow` FAST) | **52 ms** [MEASURED]; Farneback 540p 142 ms; RAFT on CPU = seconds (avoid) |
| Painterly/posterized | bilateral + k-means palette quantization (flat color regions, Scanner Darkly) | bilateral 540p **68 ms** [MEASURED] |
| Person matte | MediaPipe Selfie Segmentation / Image Segmenter (~real-time CPU), rembg u2net (~0.4 s/img), robust video matting (RVM mobilenet, temporally stable). SAM2/EfficientTAM: CPU ~1 fps or worse; BiRefNet ~15 s/img CPU — avoid. https://github.com/danielgatis/rembg/issues/687 https://github.com/yformer/EfficientTAM/issues/11 |
| Depth | Depth Anything V2-Small (ONNX, 25M) est. 0.2-0.6 s/frame @ 518px on 4 cores; Video Depth Anything-S for temporal consistency (https://github.com/DepthAnything/Video-Depth-Anything ; ONNX: https://huggingface.co/Icekender/video-depth-anything-small-onnx); DA3-Small 0.08B (https://github.com/bytedance-seed/depth-anything-3). Run at 518px, compute only on hero shots, cache. |
| Keyframe -> whole shot style | EbSynth CLI (CPU build, https://github.com/jamriska/ebsynth): paint/generate 1 styled keyframe, propagate with guides (edges, mask, position). Great for "redrawn" Seedance shots. |
| Point cloud | depth -> sample N points by luminance/edge strength -> project with slight camera orbit in WebGL (gl.POINTS) | trivial once depth cached |
| Flow particles | seed particles on edges/mask; advect with DIS flow; trail with feedback buffer in shader | cheap in WebGL |
| ASCII | downsample luminance to 16x32 cell grid; pick glyph by density ramp (` .:-=+*#%@` or custom "01" / Hanzi) — do in shader with a glyph atlas | ~free in shader |
| Halftone / dither | shader: rotated-grid dot halftone (CMYK angles 15/75/0/45), ordered Bayer 4x4/8x8, blue-noise threshold, 1-bit Atkinson (CPU, needs serial error diffusion — precompute in Python if wanted) | shader ~ms |
- Budget: Canny+XDoG+DIS+MediaPipe ≈ 150-250 ms/frame at 1080p -> 7000 frames ≈ 20-30 min on CPU. Depth on every frame
  ≈ 1 hr; restrict to shots that need it. Process at 960x540 when the look is line art (4x faster, and upscale = style).
- Temporal stability tricks: smooth masks/depth with EMA or flow-warped previous frame; quantize line positions by
  re-seeding boil every 2 frames (on twos) so flicker becomes intentional; median filter edge maps over 3 frames.

---------------------------------------------------------------------------------------------------------------------
## 4. Visual references — devices that translate to motion graphics

- **Pi** (Aronofsky 1998, DP Matthew Libatique): black-and-white *reversal* stock = crushed blacks, blown whites, no
  midtones -> 1-bit threshold look; SnorriCam (camera strapped to actor, face locked center while world swings) ->
  lock Jade's face center while background whips; "hip-hop montage" (ultra-fast repeated insert sequence: pill, pupil,
  hand, stock ticker, with a percussive sound per cut) -> perfect for builds; spiral / golden ratio, stock-ticker
  numbers scrolling, Go board.
- **A Beautiful Mind** (2001): numbers/letters in newspapers individually light up, then lines connect them into a
  pattern; wall of clippings with string -> our "proof/search" layer highlighting tokens in the lyrics or license
  plates, connecting with lines. Reveal twist: the pattern was paranoia.
- **Bad Genius** (2017, Thailand): exam as heist; split-screen synchronized clocks; extreme macro on pencils/erasers;
  silent coded hand signals (piano fingering = answers A-D); answer sheet grids filling; sweat + ticking + heartbeat
  sound design; time-zone race. -> dissertation defense = exam heist; multiple-choice bubble grid motif.
- **Primer** (2004): fan-made timeline diagrams (nested loops, "Abe 1/Abe 2") -> show loops 1/2/3 as branching timeline
  diagram; deadpan lo-fi, overlapping dialogue.
- **Tenet** (2020): red = forward, blue = inverted color coding; turnstile; temporal pincer (simultaneous forward and
  reversed action in same frame); SATOR square palindrome; reversed bullets returning to gun -> rewind the bullet
  INTO the gun; text that reads both ways ("REWIND" / mirrored).
- **Memento** (2000): color forward scenes interleaved with B&W reverse scenes; Polaroids shaking into existence with
  handwritten captions; tattoos as notes ("NEVER STOP" tattooed/handwritten); a Polaroid un-developing as rewind.
- **Braid** (2008, art David Hellman): holding Shift rewinds everything with reversed audio and a blurred, desaturated,
  ripple-distorted screen + visible "rewind speed" multipliers (x2, x4, x8); green-glowing objects immune to rewind;
  World 5 "Time and Decision" — a purple **shadow self** replays the actions you undid (= "a shadow chasing me I
  couldn't place" — the shadow is her own previous loop). Painterly watercolor parallax backgrounds.
- **Edge of Tomorrow** ("Live. Die. Repeat."): death -> hard smash cut to the same wake-up frame, gasp; montage of
  increasingly efficient repetitions, comic-timed deaths; protagonist knows the next beat before it happens (dodge
  before the shot). -> Loop 3: she preempts every beat.
- **Run Lola Run** (1998): 3 runs with tiny divergences; red hair as sole saturated element; animated cartoon segments
  for the stairwell; "und dann..." flash-forward photo strips of bystanders' futures; red-lit bed interludes between
  runs; techno at ~120-130 BPM (matches our 124). Overhead spiral clock; split-screen.
- **Severance**: endless symmetrical white corridors; retro-futurist green-on-cyan CRT; Macrodata Refinement — grids of
  numbers that jitter, swell, and are "scary" for no reason, binned into folders -> paranoia-as-data-grid; precise
  centered one-point perspective.
- **Mr. Robot** (DP Tod Campbell): extreme short-siding (subject crammed in lower corner, huge negative space), real
  terminal commands on screen, unreliable-narrator glitch cuts, fsociety mask.
- **Hotline Miami**: hot pink/cyan neon, top-down, constant screen sway/rotation, VHS chromatic split, instant death
  -> "PRESS R TO RESTART" — the bluntest possible rewind prompt. Kill-combo score popups.
- **Superhot**: "time moves only when you move" — frozen bullets with visible trails mid-air; white world, red
  low-poly enemies shattering into shards; replay at real speed; giant "SUPER. HOT." chant text slams -> "RE. WIND."
- **Chess engine analysis**: vertical eval bar (white/black, swings on blunders); eval graph across the game;
  principal-variation arrows (Lichess green/blue arrows); move annotations "!!" brilliant (teal), "??" blunder (red),
  "#3" mate-in-3; search-tree expansion (MCTS / alpha-beta pruning: branches greying out = dead lines). -> Each loop
  is a variation; shot = "??", the never-stop line = "!!". Eval bar drains toward "−M1" when the agents approach.
- Also: *Copenhagen* (Frayn, the book's epigraph) — same night replayed three ways; *Groundhog Day*; *Russian Doll*
  (death resets, mirror-shard rot); *Source Code*; *Looper*; Nolan's *Following*.

---------------------------------------------------------------------------------------------------------------------
## 5. Kinetic typography + attention design

**K-pop MV attention mechanics** (https://www.dazeddigital.com/music/article/40602/1/how-to-make-an-iconic-k-pop-music-video ,
https://ivywxy.medium.com/point-choreography-in-k-pop-d392a27089e2)
- Center = law in chorus (symmetry), asymmetry in verses; cuts on 8-counts: wide formation -> point-move close-up on the
  hook -> whip to next line. Concept/outfit set switches each section (2-4 "worlds" color-blocked). Bridge goes quiet
  before the last chorus detonates (our breakdown -> "Never stop" -> final drop).
- "Killing part"/point choreo: one repeatable signature gesture. BLACKPINK "Kill This Love" finger-gun shot is the
  canonical example — **our killing part = the finger-gun/"BAM" -> freeze -> rewind hand-spin gesture** on "Rewind."
- Typography title slams on the hook, member-name lower thirds, high-saturation monochrome sets (aespa "Supernova",
  LE SSERAFIM, ILLIT "Magnetic", NewJeans "ETA" iPhone-POV).

**Lyric typography precedents**: Saul Bass / *Psycho* titles (bars slicing text — thriller canon), Kyle Cooper *Se7en*
titles (scratched, jittering hand-made type), Gaspar Noé *Enter the Void* titles (strobing font-per-word), Weird Al
"Word Crimes" (all-type MV), Mr. Robot / Severance UI type, Pi's ticker type. Kanye *Yeezus*/Donda redacted aesthetic.
The Claude-Pop hit with a halftone portrait overlay reportedly reached 3.3M views; creators note big lyrics on screen
from frame 1 as the hook (https://legaled.ai/claude-can-now-make-music-videos/).

**Redacted / FOIA / brutalist**: black bars that slide on and off words (redaction as rhythm — bar lands on kick);
"SECRET//NOFORN" classification banners, FBI file case numbers, Bates stamps, typewriter Courier, fax/scan noise,
"[REDACTED]" replacing names, stamped "DECLASSIFIED". Real precedents: Wen Ho Lee case (FBI 1999), Qian Xuesen
deportation 1955, the DOJ "China Initiative" (2018-2022, cases e.g. Anming Hu acquittal) — all public record; a FOIA
document card in the video grounds the subtext of "Initiative" without speaking it. Internet brutalism: raw HTML
default Times/Arial, blue links, visible grid, monospace.

**Terminal/agent UI overlays**: `$ ./defense --attempt 2`, stack traces at the moment of death (`SIGKILL received`,
`segfault (core dumped)`), `git reset --hard HEAD~1` / `git checkout loop-3`, `retrying (2/∞)...`, progress bars,
token-streaming text, Claude Code-style tool-call blocks (`● Bash(run --never-stop)`), `ctrl+R` reverse-search prompt
(literal "rewind" in terminal), seed numbers (`seed=3 → survived`).

**X/Twitter first 2-3 s (2025-2026, SF tech)**
- 70-85% of X video impressions are muted autoplay; first 3 s decide distribution; **burn in captions/lyrics** (CC is
  off by default) (https://blitzcutai.com/blog/how-to-add-captions-x-twitter-video ,
  https://www.influencers-time.com/silent-first-editing-subtitle-rules-for-muted-autoplay-feeds/).
- Our intro is rubato ambient — **dangerous for retention**. Open with a high-contrast still frame that already reads:
  e.g. frame 0 = "LOOP 1/3 — p(survive)=0.00" eval bar + Jade's face + big type; tease the rewind (a 0.5 s reversed
  flash of the gunshot) in second 1. Consider a cold-open teaser of the drop.
- Formats that read instantly for this audience: eval/benchmark bar charts ("SOTA" bar), loss curves (spiky -> converged
  = loop 1 -> 3), agent logs / Claude Code terminal, "it's so over / we're so back" (shot = so over, rewind = so back),
  "the timeline" / "branching timelines", "feel the AGI", git branch graphs, seed/retry ("just reroll"), p(doom)-style
  probability meters (Claude-Pop lineage), "made entirely in code" claim in the caption (genre's proven hook).
- Text in-frame should be legible at phone size: >= 90 px cap height at 1080p for key words, max ~5 words on screen.
