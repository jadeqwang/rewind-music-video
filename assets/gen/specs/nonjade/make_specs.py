#!/usr/bin/env python3
"""Specs for the non-Jade Seedance 2.5 roto-base batch (E*/S* shots). Run: python3 make_specs.py [take]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TAKE = sys.argv[1] if len(sys.argv) > 1 else "t1"
LOOK = (" Single continuous shot, no cuts, no transitions. Night. Graphic neo-noir cinematography, photographic. Large areas of pure black, "
        "hard directional light sources with crisp edges, clean bold silhouettes, simple readable geometry, uncluttered composition, "
        "smooth surfaces, sharp focus, no motion blur smear. Palette limited to sodium-vapor orange, siren red, siren blue and cold white. "
        "No text, no lettering, no signs, no logos, no license plates, no watermark, no subtitles.")
NOPEOPLE = " No people."
SUIT = (" The men are solid pitch-black backlit silhouettes, faces completely in shadow and featureless, only the outlines of sunglasses, "
        "shoulders, ties and arms; nobody's face is ever lit.")
S = lambda p: f"file:assets/sets/{p}.jpg"
SHOTS = {
 "E1": dict(dur=10, image=S("lake_shore_drive/2"), p=
  "Slow steady forward drone flight high above Lake Shore Drive at night, following a lone car with two white headlight beams as it drives north along the long smooth curve of the empty lakefront highway. The dotted line of orange sodium streetlights traces the curve; the pitch-black lake on the right stays flat and still. The camera glides forward smoothly and continuously, keeping the car in the lower middle of the frame." + NOPEOPLE),
 "E2_calm": dict(dur=6, image=S("lake_shore_drive/1"), p=
  "Driver's point of view from a car driving steadily north on an empty curving lakefront highway at night. The road flows toward the camera at a calm cruising speed: white lane dashes and the evenly spaced orange sodium streetlights slide past one after another in a steady rhythm. Camera locked to the car, smooth forward motion, only the top edge of the black dashboard at the bottom of frame. The flat black lake on the right." + NOPEOPLE),
 "E2_fast": dict(dur=8, image=S("lake_shore_drive/1"), p=
  "Driver's point of view from a car racing at very high speed along an empty curving lakefront highway at night. White lane dashes rush toward the camera and the orange sodium streetlights whip past overhead in fast streaming flashes, one after another. Camera locked to the car, fast smooth forward motion, only the top edge of the black dashboard at the bottom of frame. The flat black lake on the right." + NOPEOPLE),
 "E3_flood": dict(dur=5, refs=[S("car_interior/1")], p=
  "Inside a dark empty car driving at night, from the driver's seat looking forward over the steering wheel; nobody is in the car. Locked-off camera. The large rear-view mirror at the top center of the frame starts dark, then slowly fills with pulsing red and blue emergency light from a vehicle far behind, until the mirror glows bright red and blue. Through the windshield the dark highway with orange sodium streetlights passing. Dashboard almost black, the steering wheel a clean black silhouette ring." + NOPEOPLE),
 "E3_follow": dict(dur=5, refs=[S("car_interior/3")], p=
  "Close-up of a car's rear-view mirror at night, filling most of the frame, locked-off camera. In the dark mirror two small white headlights of a car far behind follow steadily, slowly growing closer. Then soft red and blue emergency light starts pulsing around them and gradually floods the mirror. Outside the mirror, the black interior and a few orange sodium lights through the windshield." + NOPEOPLE),
 "E4": dict(dur=6, image=S("grass_field/3"), p=
  "Low camera among a few tall grass stalks at night, locked-off. The tall stalks sway in a strong wind as clean dark silhouettes. Two hard white flashlight beams sweep slowly side to side through faint mist, raking across the grass and cutting bright shafts through the black air." + NOPEOPLE),
 "E5": dict(dur=10, image=S("defense_room/1"), p=
  "A very slow, smooth, steady dolly push-in through an empty dark university seminar room toward the single empty chair alone in the middle of the floor, which faces a long table with five empty chairs behind it. The projector beam stays hard and white, the fluorescent ceiling panel stays steady. Nothing else moves. The blank chalkboard stays completely blank." + NOPEOPLE),
 "Epull": dict(dur=4, refs=[S("lake_shore_drive/3"), S("pullover/1")], p=
  "Exterior side view at night on a dark lakefront highway: a small dark hatchback car slows down, its red brake lights glowing, and steers onto the paved shoulder until it comes to a stop. Right behind it a black sedan follows and stops too, its two headlights blazing hard white light that throws long shadows across the smooth asphalt. Orange sodium streetlights, black lake beyond. Steady camera." + NOPEOPLE),
 "S1": dict(dur=5, image=S("pullover/1"), p=
  "Four tall men in identical dark suits and sunglasses walk slowly and steadily toward the camera in a tight symmetrical V formation along the dark road shoulder, backlit by the blazing white headlights of the black sedan behind them, long shadows stretching toward the camera. Locked-off low camera. Always exactly four men." + SUIT),
 "S2": dict(dur=4, refs=[S("car_interior/2"), S("pullover/1")], p=
  "From inside a dark parked car at night, looking out through the driver's side window. A tall man in a dark suit stands right outside the window, a solid pitch-black silhouette against the blazing white headlights of a sedan behind him; only the outline of his head, sunglasses, shoulders and tie. He slowly raises one arm toward the window. Locked-off camera, the window frame a clean black shape." + SUIT),
 "S3": dict(dur=6, refs=[S("grass_field/1"), S("pullover/1")], p=
  "Wide shot at night of a field of tall grass: four men in dark suits run fast through the waist-high grass from left to right, solid pitch-black silhouettes. Hard white flashlight beams sweep across the field and rim-light their shoulders and the grass tops. Black sky, a thin row of orange lights on the far horizon. Steady camera panning slightly to follow." + SUIT),
 "S4": dict(dur=10, image=S("defense_room/1"), p=
  "Locked-off camera in the dark university seminar room. One by one, five men in dark suits walk in from the darkness and sit down in the five empty chairs behind the long table, until all five chairs are occupied and the men sit perfectly still facing the lone empty chair in the foreground. They are backlit silhouettes against the projector glow and the fluorescent panel." + SUIT),
 "S5": dict(dur=6, refs=[S("lake_shore_drive/1"), S("pullover/2")], p=
  "Camera mounted low on the side of a car speeding along a lakefront highway at night, looking sideways at the road shoulder. Four men in dark suits stand still in a row on the shoulder under orange sodium streetlights, and the camera rushes past them at high speed, so they slide quickly across the frame from right to left and are gone. Smooth fast lateral tracking motion." + SUIT),
}
if __name__ != "__main__": SHOTS = {}
for k, s in SHOTS.items():
    inp = {"prompt": s["p"] + LOOK, "duration": s["dur"], "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": False}
    if "image" in s: inp["image"] = s["image"]
    if "refs" in s: inp["reference_images"] = s["refs"]
    spec = {"model": "bytedance/seedance-2.5", "tag": f"nj_{k}_{TAKE}", "notes": f"non-Jade roto base {k} {TAKE}", "input": inp}
    json.dump(spec, open(os.path.join(HERE, f"{k}_{TAKE}.json"), "w"), indent=1)
if SHOTS: print("wrote", len(SHOTS))
