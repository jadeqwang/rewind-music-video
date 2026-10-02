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
- Her two eyebrows are slightly DIFFERENT from each other (natural asymmetry, part of her likeness). Never symmetrize.
  Measured per side in measure.json; beware mirrored front-camera selfies when deciding left/right.
- Redraw: draw each brow from its own measured shape, not one mirrored brow.
- FACE SHAPE (user correction): heart-shaped / "melon seed" (瓜子脸) — wide forehead & cheekbones, tapered jaw, narrow
  softly pointed chin. Plates E and H were wrong here (too round/wide-jawed). Gate measures jaw/cheek and chin taper.
- FOREHEAD/UPPER HEAD (user clarification): G's face shape is nearly right; the TOP HALF OF THE HEAD must be larger —
  a large forehead is a defining trait. NEVER prompt "raise/increase hairline" (models make her bald without growing
  the head). Prompt "large tall broad forehead, larger upper head", or warp the whole region above the brows
  (forehead + cranium + hair together) upward; lower face untouched.
- EYES: slight, thin double-eyelid crease (not monolid, not a deep crease). Redraw it as a fine line.
- HAIR: half-up half-down in TWO SYMMETRICAL PIECES (top section gathered left+right of the center part toward the
  crown; rest long and straight). Invisible head-on, adds volume up top and accentuates the large upper head. Show in
  3/4, profile and back views; include in every prompt.

## Strategy (user, from the Orbital Sunrise lesson)
Prefer her REAL PHOTOS as the base: choose shot angles that match an existing photo's camera, composite her (real face
pasted back, pixel-exact) into the set plate, relight with simple grading, and use that as Seedance's first frame,
with the real photos as reference_images. Generated character sheets are backup for wides/full-body only.

## Approval state (2026-10-02 night)
User: "yes, generate the shots but don't animate them all just yet." → all Jade first-frame stills OK; max 2 validation
animations (J1, J6). Everything else waits for morning review.
- VIDEO FINDING: Seedance shrinks her eyes progressively within a clip (iris −7..−19%). So the redraw uses footage
  landmarks only as anchors/pose; eyes/brows/crease are drawn from the canonical real-photo template. Mouth from the
  vocal stem. Seedance lip-sync leads by a constant ~0.29 s (cut reference audio to start at the first sung word, or
  shift video +0.29 s). Seedance needs use_virtual_avatar:true for her face (else error 7003).
- POSE CONGRUENCE (user): head pose and body pose must agree in every composite/frame (J9 failed: face pointed a
  different way than the body → uncanny; J6 is the good example). Performance/center-lock shots (J5, J5b) use a
  straight-on frontal photo (yaw≈0). Measure head yaw/pitch/roll and pose the body around it; verify shoulder line.
