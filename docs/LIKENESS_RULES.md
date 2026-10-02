# Likeness rules for Jade (hard constraints for every agent)

The user reports most model attempts "uglify" her: shrunken eyes, invented age spots, aging. Treat this as a P0 quality bar.

## Generation (Grok Imagine / Seedance)
- ALWAYS condition on the user's real photos (refs/jade/) — never text-only descriptions of her face.
- Character sheet first, approved by the user before ANY shot generation. No shot gens with an unapproved sheet.
- Face lighting in the sheet: soft, even, frontal key. Hard/colored light only in shots, never as the sheet's face light.
- BANNED words anywhere a face is visible: gritty, raw, harsh, realistic skin texture, pores, film grain, weathered,
  tired, exhausted, haunted, gaunt, aged, dramatic shadows on face, squinting, wrinkles, freckles/spots, desaturated skin.
  Express anxiety through posture, hands, framing, light and motion — not by degrading the face.
- Include positive anchors: "same face as reference, same eye shape and size, smooth clear skin, youthful, accurate likeness".
- Reject any output with smaller eyes, changed eye shape, added marks/spots/lines, older apparent age, or altered face shape.
  Compare side-by-side with the reference photos at the same crop before accepting (visual review, every take).

## Redraw (our JS/roto layer)
- Jade is a flat bone-white fill with SPARSE interior lines. Inside the face region keep only: eye outlines (at
  reference size — never thin/shrink), brows, a nose-tip mark, lips, jaw/hair contours. Suppress all other face edges
  (no texture, no hatching on skin, no spots, no under-eye lines). Hatching faces looked bad in Orbital Sunrise.
- Eyes may be traced from the reference sheet geometry rather than the gen footage if the footage drifts.
- Mouth shapes come from the vocal track, not the gen footage.

## User feedback round 1 (authoritative)
- Plate G (DRIVER_PLATE_y27) is "almost right" but the FOREHEAD IS TOO SMALL vs her natural look. All other candidates
  "subtly shrank my eyes for no reason". Known model biases: compressed forehead/low hairline, shrunken eyes.
- Gate: every image/frame of Jade is measured with tools/likeness/measure.py against the real-photo ratios
  (assets/character/v2/measure.json); deviations > ~5% in eye size or forehead height are corrected (warp.py) or rejected.
