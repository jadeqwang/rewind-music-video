# assets/car: white 2001 Acura TL (2nd gen) kit for the JS renderer

Seedance won't draw her car (CLIPS.md), so the renderer draws it from this kit. Tools are in `tools/car/`:
`gen.py` (stills, every prompt logged in `prompts.json`), `process.py` (matte, lines, contours, CAR_SHEET) and `track.py` (clip tracks).
Contact sheet: `CAR_SHEET.jpg`. Its columns are ref | matte | line art on ink | contours.json rendered.

## Views (`<view>/{ref.jpg, matte.png, lines.png, contours.json}`)
| view | use | source |
|---|---|---|
| `chase` | **E1** (drone directly behind and above, centred). Best match to the E1 framing | gpt-image-2 |
| `rear34` | E1 variant / any off-axis follow shot (rear-left, elevated) | gpt-image-2 |
| `rear` | mirror ghost car / being followed (bumper height, tail lights on) | gpt-image-2 |
| `side` | **Epull** pull-over (faces LEFT, LHD driver side) | grok-imagine-image-quality |
| `front34` | S5 / passing suits, headlights on (front-left) | grok-imagine-image-quality |
| `top` | aerial / map overhead, nose UP (1:1) | grok-imagine-image-quality |

The silhouettes were checked against the 1999–2003 TL: rounded body, short deck, slim wraparound headlights, the
trapezoid wraparound tail lights, and a 6-window greenhouse. Modern-looking and Accord-looking candidates are in
`analysis/car/cands/` and were rejected. Plates are blank. The only marking is a tiny caliper badge with no letters.

- `matte.png`: 8-bit soft alpha (rembg isnet, largest component, holes filled), at the ref resolution.
- `lines.png`: RGBA, white contours on transparent. It is made by applying 3x bilateral, then CLAHE, then XDoG and Canny inside the eroded matte, skeletonizing, removing specks, and adding the silhouette. Lines are about 3 px at 1536 wide.
- `contours.json`: `features[] = {type, closed, pts:[[x,y]..]}`. Coordinates are in a unit box: they are scaled by max(bbox w,h) of the car, the origin is the bbox top-left, and y points down.
  `extent` = [w,h] in those units. `anchor_ground_center` = bottom-centre (place this on the road).
  Types: `body` (outer silhouette), `window`, `wheel`/`tyre`/`rim`, `taillight`, `headlight`, `lower_dark` (intakes, wells), and
  `detail` (the 40 longest open strokes from the line art: panel seams, trunk lip, bumper). For a clean minimal car, draw
  body+window+wheel/rim+lights. Add `detail` at lower alpha for richness.

## Renderer recipe
1. Per frame, take the clip's track bbox (below) and map the view's unit box so that `extent` fits the bbox. Scale uniformly by the bbox width, and anchor the bottom-centre to the bbox bottom-centre.
2. Erase the Seedance car: fill `matte.png` (scaled the same way, or simply the bbox, dilated) with ink before drawing, so the
   dark modern sedan never shows through.
3. Draw the polylines with your line boil (per-vertex jitter ±0.3–0.6 px, re-seeded every 2–3 frames). Do NOT jitter `body`
   more than `detail`, because the silhouette must stay steady. Tail lights: fill siren-red #FF2A2A with glow. Headlights: cold white, plus a beam cone.
   White paint = bone/cold-white lines. Optionally add a faint matte fill at 5–10% so the car reads as WHITE against the ink.
4. Below about 60 px car width (E1 f14–110), draw only `body` + `taillight` (and maybe `window`). Detail lines would turn into noise.
5. As a fallback, composite `lines.png` instead of the vectors (it is crisper at 1:1 but doesn't boil per-vertex).

## Tracks (`tracks/<clip>.json`, source px 1280x720 @24 fps, plus `bbox_norm`)
- **E1.json**: tracked backwards from f240 on the red tail-light pair. The bbox is derived from the light span: w=1.12·span,
  top=ly−0.53·span, bottom=ly+0.42·span. Visible f14–240. f0–13 show the oncoming car leaving the bottom edge, which is not her car. Use
  `chase` (or `rear34` early, when the camera is higher). Verified overlay: `analysis/car/track_E1.jpg`.
- **Epull.json**: the lead car's leading-end light cluster, with static streetlights removed by a median background. bbox from the
  perspective length L(y)=85+0.37·(y−220) px along the road. The road slope is about −0.36, so rotate `side` by about −20° and keep it facing left (direction of
  travel). Seedance flips the car mid-clip (white lights at the leading end until about f40, red after). Ignore that and draw our TL
  consistently, with brake lights from f40. Known error: **f0–20 bbox sits about 40 px too low** because it locks on the wet-road reflection.
  Shift those frames up or hand-key them. The follower (black sedan headlights, upper right from about f40) is not tracked. Overlay:
  `analysis/car/track_Epull.jpg`.
- **S5** has no car in frame (the camera is in her car). Use `front34`/`side` only if a passing-car insert is wanted.
