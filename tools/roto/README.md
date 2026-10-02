# tools/roto — clip -> roto layers for the renderer

`python3 tools/roto/roto.py <SHOT> [--start s --dur d] [--layers lines,matte,light,flow,face] [--workers 3] [--force]`
reads `assets/clips/<SHOT>.mp4` (or `--src`) and writes `assets/roto/<SHOT>/` (or `--out`). `--all` does every clip
whose roto is missing or older than the clip; `--watch A,B --minutes 60 --every 4` keeps polling for new clips.
Resumable (per-frame `.parts/NNNN.json` written last), 3 worker processes over contiguous frame chunks.
Format details are in the docstring at the top of `roto.py`; per-shot settings in `SHOTS` (persons channel, RVM ratio,
car, grass, skyline cut, line overrides).

- **lines** (`lines.py`): 960x540 analysis. Per-shot gamma lift (stable in time) + CLAHE, fast-global-smoother
  flattening, Canny + band-pass strength, skeleton -> traced paths split at real junctions; drop short / weak /
  wiggly / texture-dense paths, kill point-light halos and skyline dot fields; coarse 480x270 pass for soft big edges;
  bridge small gaps; Gaussian-smooth each path and draw at 1080p (4x supersampled) with strength-weighted, tapered
  strokes (~1.7-3.2 px).
- **matte**: persons = Robust Video Matting (mobilenetv3 ONNX, recurrent = temporally stable; MediaPipe deeplab /
  selfie / pose all fail on these backlit silhouettes); car = ISNet salient object gated by EfficientDet car boxes.
  Flow-warped EMA, guided-filter edge snap to the Lanczos-upscaled 1080p frame. `matte/` = primary subject alpha,
  `mattes/` = packed RGB (R jade, G suits, B car). Suit face-bar boxes + glints come from head peaks on the matte.
- **light**: HSV classification at 480x270 -> red / sodium / blue / cold-white strengths (+ ground, luma) atlas.
- **flow**: DIS (medium) at 480x270 -> 240x135 companded PNG.
- **face** (J shots): MediaPipe Face Landmarker -> features (lids + fine crease, iris, per-side brows, nose-tip mark,
  lower jaw), face mask (lines suppressed), refined hair mask, `face.json` polylines, mouth/tilt; likeness gate from
  `tools/likeness/measure.py` every 3rd frame -> `per_frame[i].likeness`, flagged frames in `meta.likeness_flags`.
  Glasses extraction exists but is off (`glasses: True` per shot) because broken frame rims read as under-eye lines.

Models are fetched on first use into `tools/roto/models/` (gitignored): GitHub releases (RVM, ISNet) and
storage.googleapis.com (MediaPipe). PNG layers are gitignored; commit `meta.json`, `face.json`, `preview.jpg`.
