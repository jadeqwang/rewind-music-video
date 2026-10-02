# REWIND — Treatment (v1, director's draft)

## Working title card
**REWIND** — *a proof by exhaustion*

"Proof by exhaustion" is a real method: you prove a theorem by checking every case. That's the dream, the defense,
and the anxiety brain in one phrase. A dissertation is a proof you defend. The nightmare is a game you replay.
The way out isn't courage, it's search: enumerate the branches, prune the ones where you die, keep going.

## The one idea
**The search tree is the road.** Every attempt is a branch. Every death is a pruned leaf (✗). The final branch that
survives is drawn as one continuous line — and that line is the curve of Lake Shore Drive along the lake.
The last image: the whole tree of failed futures collapses into a single highway that never ends. NEVER STOP.

## Visual style: "REDACTED NOCTURNE" (working name)
A rotoscope style we invent, drawn entirely in JS canvas, over Seedance-generated base footage that is never shown raw.

- **World = luminous contour lines** on ink black. One-weight strokes derived from the base footage (edges + depth
  contours), like a LIDAR scan / oscilloscope / chalk on a blackboard. Lines *boil* on twos (12 fps redraw jitter)
  so it feels hand-drawn, while camera, text and light move at a full 30 fps.
- **Jade = solid bone-white flat fill** (a cut-paper silhouette with sparse interior lines). She is the only "solid"
  thing in the world. When she's a past self/ghost in a rewind, she becomes outline only.
- **The suits = REDACTION.** The men in shades and suits are drawn as pure black cut-outs with a black bar where the
  face is (FOIA redaction), only the sunglasses catch a glint. They are literally "a shadow I couldn't place".
  Subtext from *Initiative*: Wen Ho Lee, Qian Xuesen, "pack a go bag". The state as a redaction.
- **Light = the only color.** Siren red #FF2A2A and siren blue #2F5BFF flood the frame as flat fills, alternating
  on the beat. Sodium-vapor orange #FF9F1C for Lake Shore streetlights. Everything else: ink #07080A, bone #ECE6D8.
- **Thesis typography.** Whispered verses are set in Computer Modern italic (the LaTeX dissertation face) like
  a page of the dissertation; drops are a massive condensed grotesk; HUD/system text in a mono. A thin rule, a page
  number, a footnote marker — the dissertation document is the UI of the nightmare.
- **Search/engine HUD.** Chess-engine evaluation bar (left edge) that swings toward death as threat rises
  (eval: +0.3 → −#1 "mate in 1" right before the shot). Move notation for her choices: `1. pull over?!`,
  `1. bolt?`, `1. keep driving!!`. Attempt counter: `ATTEMPT 01`. Pruned-branch tree grows at screen edge.
- **Braid rewind.** On every shot: freeze (Superhot stillness) → bullet suspended as a drawn line → frame inverts
  to negative → everything runs backwards with motion-echo ghosts (trails of previous frames), a timecode counter
  spinning backwards, tape-stop warble matching the audio's tape stop, the ✗ stamped on the branch.

## Hook (first 3 seconds)
Cold open **at the death, rewinding**. Frame 1: frozen muzzle flash, suspended bullet, red/blue flood, giant text
`ATTEMPT 01 ✗`. Then a 2-second reverse scrub through the whole video at high speed (a trailer in reverse — shows
the style, the sirens, the field, the tree) landing on the dark road. Then big text in Computer Modern:
*"The night before my dissertation defense,"*. Everyone on the timeline who has a PhD, defended anything, or had the
exam nightmare is hooked by the line + the rewind.

## Structure (timings to be locked from analysis/timing.json)
| Section | Lyric | Visual plan |
|---|---|---|
| Intro (rubato, rain, kalimba) | — | Cold-open rewind hook → rain on windshield drawn as falling line segments; dashboard glow; the lake is a black void with one moving contour. Title card REWIND / *a proof by exhaustion*. |
| Verse 1 (whispered) | The night before my dissertation defense… shadow chasing me | Lyrics LARGE, left 2/3, Computer Modern italic, word-by-word. Jade at wheel right third. Lake Shore Drive streetlights strobe past (sodium orange). Rear-view mirror insert: a shadow with no source. Footnote markers on words ("defense¹" → footnote: "¹ tomorrow, 9:00 AM"). |
| Build 1 (cello ostinato, ticking clock) | I pulled over… men in shades and suits… reach for ID… and I do… shot… time stops | Clock-tick cuts on 8ths. Sirens begin (SILENT in the poem → we show light without sound-wave). Car stops. 3–4 redacted suits approach in formation (K-pop formation logic: center-framed, symmetrical). ID card insert: NASA badge, her photo as silhouette. Eval bar collapses. "With no warning" → hard freeze. |
| Tape stop + silence | — | Absolute black. One white line (the bullet). Silence = an empty frame with tiny mono text `time stops`. |
| Drop 1 | Rewind. Rewind. | REWIND typography the full frame, stuttering with the vocal chops; negative inversion; everything from build 1 plays backwards in ghost trails; the tree draws its first ✗ branch. Braam = full-frame flood. |
| Verse 3 | And now I'm back on the road / sirens in my mirror… Reload / race | `ATTEMPT 02`. Same road, now the HUD is armed. "Reload." = a gun/save-state glyph, the whole frame snaps (like reloading a save). Mirror fills with red/blue. |
| Build 2 (taiko, Shepard riser) | I zigzag across the field of grass / they're just too fast / shot / time stops | Field of grass as thousands of line strokes bending in wind (procedural). Top-down chess-board view: her path as a zigzag line; suits' paths converge (pursuit curves, mathematically drawn). Shepard riser = infinite scrolling. Shot → freeze. |
| Tape stop + silence | — | Black. ✗ |
| Drop 2 (darker, stutter) | Rewind. | Heavier. The tree has two pruned branches; the rewind now shows BOTH previous deaths overlaid. Glitch stutter typography; redaction bars sweep across the screen covering the lyric. |
| Breakdown (kalimba, whispered stacks) | The night before my dissertation defense… (repeat) | Quiet. The dissertation room: an empty defense table, chairs, a projector beam. Committee = the same redacted silhouettes, seated. Lyrics stack and repeat (vocal stacks) as overlapping Computer Modern lines, like revisions/track changes. Brilliant-mind montage: equations, the map of LSD, timestamps pinned with red string — A Beautiful Mind wall. |
| Build 3 (Phrygian horror, heartbeat) | Never stop. | Brute force. The search tree explodes: thousands of branches drawn in milliseconds, each ending in ✗; eval bar thrashing; attempt counter spinning 03…999…; heartbeat kick = frame pulse. Then one branch stays lit. |
| Final drop | — | `ATTEMPT 03 — LINE FOUND`. She doesn't pull over. Car keeps driving; sirens fall behind/peel away; the suits remain at the roadside getting smaller. The surviving branch IS Lake Shore Drive. Speed lines; four-on-the-floor = streetlight strobes on every kick. NEVER STOP lyric giant, then broken into the road's lane dashes. |
| Instrumental → abrupt end | — | Relentless driving; tree collapses into one line; at the abrupt end: hard cut to black, one mono line: `∎` (Q.E.D.). Or the defense: "Questions?" Hold 0 frames — just cut, like the song. |

## Rules of composition
- Big-lyric shots: background quiet (one or two contours), Jade right third, text left two-thirds.
- Subtitle shots: text bottom-center in mono, small, when the image carries the moment (shot, rewind, field).
- Cut on the beat; change shot on downbeats in drops; hold longer in verses. Never let both the background and the
  text be busy at the same time.
- Every death and rewind must be instantly legible without sound (Twitter autoplays muted): ATTEMPT counter,
  ✗, REWIND text, and visual reverse motion.

## Core tension (user, authoritative): SURREAL/DREAMLIKE and HIGH ENERGY at the same time
Rule of thumb: **dream logic in SPACE, club energy in TIME.** Geometry, causality and continuity are wrong like a dream;
rhythm, cutting and impact are relentless like a club.
Dream devices (use throughout, sparingly but constantly):
- Impossible continuity: match-cuts by shape (steering wheel → clock face → tree root node → defense-room table);
  the road loops back into itself; streetlights repeat infinitely (visual Shepard tone); the lake is a black mirror
  reflecting the road upside-down; the mirror shows a different time than the windshield.
- Lag / desync (from the book's "Know the place for the first time": "audio and visual input would fall out of sync,
  creating a lag"): ghost layers trailing a few frames behind; a second outline of Jade that moves a beat late.
- Scale slips: the suits are sometimes too tall, sometimes tiny on the horizon in the same shot; the car interior is
  too deep; the defense room has too many chairs.
- Floating calm inside violence: one element in slow motion (rain, bullet, hair) while everything else cuts on 16ths.
- Text behaves like dream text: words re-spell themselves, letters drift out of the line, the page breathes.
Energy devices: cut on kicks/downbeats in drops, 2–4% zoom punches, strobe on four-on-the-floor, camera shake on
impacts, speed lines, stutter frames on vocal chops, never a static frame > 2 bars outside the verses.
- **"Caffeine nap vibes"** (user): wired-but-asleep, the hypnagogic edge. Devices: BLINK wipes — black eyelid bars close
  top+bottom for 2–4 frames and reopen on a slightly different frame (microsleep at the wheel = dropped time);
  hypnagogic JERK — the falling-jolt snap (hard 1-frame vertical jump + flash) at each rewind's start; heart racing
  under a calm surface (heartbeat-synced vignette pulse even in quiet verses); vision going soft at the edges then
  snapping sharp on the beat; a radio-static whisper layer of text. The rewind itself is waking up inside the dream.
