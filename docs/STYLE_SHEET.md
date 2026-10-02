# REWIND — Style sheet for generated SET / ENVIRONMENT references

These plates are reference images for Seedance 2.5 (`reference_images`) and the source for our JS rotoscope.
The rotoscope redraws them as white contour lines on ink black, with flat siren-red/blue and sodium-orange light floods.
Gen pixels are never shown raw. Every exact prompt, model, seed and param is in `assets/sets/prompts.json`.
Code is in `tools/sets/gen.py` (job runner: writes images and logs prompts), `tools/sets/sheet.py` (contact sheet plus XDoG line row) and `tools/sets/style.py` (suffix and canonical prompts).

## Palette (matches TREATMENT.md)
| role | hex | in-prompt word |
|---|---|---|
| ink / world | #07080A | "large areas of pure black" |
| bone (Jade only, never in sets) | #ECE6D8 | — |
| siren red | #FF2A2A | "siren red", "red and blue emergency light" |
| siren blue | #2F5BFF | "siren blue" |
| sodium streetlight | #FF9F1C | "sodium-vapor orange" |
| headlight / fluorescent / projector | cold white | "hard white", "cold fluorescent" |

## Shared style suffix (append to every set prompt, verbatim)
```
 Night. Graphic neo-noir cinematography, photographic, 16:9 widescreen film still. Large areas of pure black, hard directional light sources with crisp edges, clean bold silhouettes, simple readable geometry, uncluttered composition, smooth surfaces, sharp focus. Palette limited to sodium-vapor orange, siren red, siren blue and cold white. No text, no lettering, no signs, no logos, no license plates, no watermark.
```
For sets with no people, also add ` No people.` For the suits plates, leave it out and spell out the silhouette, as in the pullover prompt below.

**Extra-angle prefix** (send the winner as the reference image):
- Small move: `Same location as the reference image: same design, same lighting, same palette and mood. New camera angle: <angle>.`
- Big move (high to low, top-down to close-up): `Use the reference image only for the location's look, lighting and palette, but compose a completely different camera angle: <angle>.`

The "Same location" wording makes the models copy the reference almost exactly (grok-2.0 returned the same picture), so use the second form for any large change.

## Lighting rules
1. Every frame needs 1–3 named, hard light sources: a sodium streetlight row, a headlight pair, the red/blue glow, a fluorescent panel, a projector cone. Avoid ambient fill. The darkness is the canvas.
2. Light should come from the side or from behind (rim and backlight), so shapes read as silhouettes. Suits are always backlit by sedan headlights.
3. Red and blue only ever come from somewhere: the mirror, distant behind the car, a window reflection, the frame edges. Keep it out of the middle of the frame so the JS flood owns it.
4. Make skies and the lake one flat black void. The skyline should be small and distant: close skylines turn into a thousand lit-window dots, which is line noise.
5. Ask for smooth surfaces. Wet or rough asphalt under headlights still breaks into speckle when lines are extracted, so raise the line threshold in the bright road areas.

## Canonical prompts (winners). The full text plus the suffix is in prompts.json and tools/sets/style.py `P[...]`.
| set | file | key | model |
|---|---|---|---|
| Lake Shore Drive POV | `assets/sets/lake_shore_drive/1.jpg` | `lsd_pov` | gpt-image-2 |
| LSD aerial, lone car | `lake_shore_drive/2.jpg` (3 = low tracking, 4 = chase cam) | `lsd_aerial` | gpt-image-2 |
| Car interior, mirror | `car_interior/1.jpg` (2 = passenger side, 3 = mirror close-up) | `interior` | gpt-image-2 |
| Pull-over, 4 suits | `pullover/1.jpg` (2 = reverse from behind suits, 3 = high wide) | `pullover` | gpt-image-2 |
| Grass field | `grass_field/1.jpg` (2 = elevated, 3 = low grass-stalk silhouettes) | `field_v2` | grok-imagine-image-quality; 3 is gpt-image-2 |
| Defense room | `defense_room/1.jpg` (2 = reverse from the committee side, 3 = side) | `defense_v2` | gpt-image-2 |
| Search-space tree | `search_space/1.jpg` (2 = oblique, 3 = simple binary fork) | `search` | grok-imagine-image-2.0; 3 is gpt-image-2 |

Composition phrases that worked:
- "symmetrical frontal composition", "in a tight symmetrical V formation"
- "a single empty chair with its back to the camera"
- "only the top edge of the black dashboard"
- "the flat black void of Lake Michigan on the right"
- "like a decision tree drawn in light"
- "Very simple, lots of empty black"

Suits (faceless): "solid pitch-black backlit silhouettes, faces completely in shadow and featureless, only the outlines of sunglasses, shoulders, ties and arms". I checked this at full resolution and the faces are unreadable. The base grok-imagine-image model still lit the faces, so do not use it for suits.

## Banned words
- **Sets:** text, sign, billboard, street name, exit, plate number, "Chicago" painted anywhere, poster, writing on the chalkboard. Phrase things positively ("completely blank clean black chalkboard") and keep the negative "No text…" tail. No model invented lettering in any of the 56 outputs. The car in `lake_shore_drive/3.jpg` has a blank, light-smeared plate area.
- **No faces of Jade in any set gen** (LIKENESS_RULES). Her likeness comes only from the real photos in refs/jade/. If a set prompt ever contains a person who is not a suit silhouette, it falls under every banned word in `docs/LIKENESS_RULES.md`: gritty, raw, harsh, realistic skin texture, pores, film grain, weathered, tired, exhausted, haunted, gaunt, aged, dramatic shadows on face, squinting, wrinkles, freckles/spots, desaturated skin.
- Avoid "film grain", "gritty" and "texture" in sets too. They add fine texture that boils when redrawn.

## Model comparison (same prompts; sheets in analysis/sets/r1_sheet, r2_sheet, r5a, r5b, A_*, B_*)
| model | $/img | time | verdict |
|---|---|---|---|
| **openai/gpt-image-2** (medium, 1536x1024, center-cropped to 1536x864) | ~$0.06 | 24–29 s, **close to the 30 s proxy cap**; with a ref image ~28 s | **Best overall.** Best prompt adherence (counts, layouts, the lone chair, blank boards), clean graphic darkness, best faceless suits, follows angle changes when given a reference. Run ≤4 in parallel. |
| xai/grok-imagine-image-2.0 | $0.04 | 15–20 s | Very graphic and clean. The search tree is the best of all models. Ignores angle changes when given a reference. |
| xai/grok-imagine-image-quality | $0.05 | 6–8 s | Fast and dramatic: light beams, red/blue bloom. Gave the cleanest grass field. Weaker counting (5 suits, chairs misplaced). |
| xai/grok-imagine-image | $0.02 | 7 s | Good for cheap exploration. Lights the suits' faces, so do not use it for suits. |
| google/nano-banana-pro | ~$0.14 | 18–25 s | Good room layout, but dimmer and flatter. Added a strange red ring vignette to the suits plate. Not worth the price. |
| bytedance/seedream-5-pro / -5-lite | $0.045 / 0.035 | **>30 s, times out** at 1536x864 and 2K | Unusable synchronously. These attempts may have been billed. |
| black-forest-labs/flux-2-pro-preview | ~$0.045 | 11 s | Generates, but the output URL is on `delivery.*.bfl.ai`, which the proxy blocks (403). Unusable here. |

## What the models do well and badly (for the rotoscope)
- Good: streetlight rows, lane dashes, the curve of the drive, mirror and windshield frames, the steering-wheel ring, chair and table geometry, the projector cone, backlit suit outlines, the glowing interchange tree. All of these extract as clean XDoG/Canny contours (`*/contact_sheet.jpg`, `analysis/sets/canny_flood_test.jpg`).
- Good: the hue-threshold flood test pulled out clean red, blue and orange regions (the mirror burst, the sodium road wash, the window reflections), so the JS flood can key on these plates directly.
- Bad: **grass becomes thousands of tiny strokes**. Use the field plates for horizon, beams and layout only, and draw the grass procedurally as the treatment already plans. `grass_field/3.jpg` (a few big stalks) is the exception and redraws well.
- Bad: distant skylines turn into a mass of window dots, so mask them or replace them with a simple drawn silhouette. Lit asphalt turns into speckle. The plates are very dark, so apply CLAHE or gamma before extracting lines.
- The base grok model sometimes lights the suits' faces. gpt-image-2 frames are 3:2 natively, so crop them (gen.py does this).

## Budget
The estimated total is about $3.3 for the logged images, plus about $0.25 for the timed-out Seedream calls and the Flux calls whose downloads were blocked. The budget was ~$8. No video was generated.
