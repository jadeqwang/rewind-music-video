# assets/sets — environment reference plates (no faces; suits are faceless silhouettes)
- `<set>/1.jpg` is the hero plate; `2.jpg`, `3.jpg` (and `4.jpg` for lake_shore_drive) are extra angles made with 1.jpg as the reference image. lake_shore_drive: 1 = POV, 2 = aerial, 3 = tracking, 4 = chase.
- `<set>/contact_sheet.jpg` shows the plates with an XDoG line test underneath. `<set>/candidates/` holds the rejected candidates. `_modeltest/` holds the model comparison runs.
- `prompts.json` has the exact prompt, model, seed (null = the model has no seed), params, reference images and status for every image.
- Regenerate with `python3 tools/sets/gen.py jobs.json`. The style guide is in docs/STYLE_SHEET.md.
