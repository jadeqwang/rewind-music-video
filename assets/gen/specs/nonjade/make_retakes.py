#!/usr/bin/env python3
"""Retake (t2) specs for shots rejected in review. Shares LOOK/SUIT with make_specs.py."""
import json, os
from make_specs import LOOK, SUIT, NOPEOPLE, S, HERE
R = {
 "E2_fast": dict(dur=8, image=S("lake_shore_drive/1"), p=
  "Driver's point of view from a car racing extremely fast, far above the speed limit, along an empty curving lakefront highway at night. The white lane dashes strobe toward the camera in rapid succession and the tall orange sodium streetlights rush past overhead every half second, one after another, flashing by the left edge of the frame. Strong, fast, continuous forward motion, the camera locked to the car, only the top edge of the black dashboard at the bottom of frame." + NOPEOPLE),
 "E4": dict(dur=6, image=S("grass_field/3"), p=
  "Low camera among a few tall grass stalks at night, locked-off. A strong gusting wind bends and whips the tall stalks back and forth as clean dark silhouettes. Two hard white flashlight beams sweep quickly across the frame in wide arcs from left to right and back, raking through the grass and the faint mist, so bright shafts and deep black gaps move constantly across the field." + NOPEOPLE),
 "Epull": dict(dur=4, refs=[S("pullover/3"), S("lake_shore_drive/3")], p=
  "High wide shot from beside a dark lakefront highway at night, steady camera. A small dark hatchback car drives along the highway from right to left, brakes with its red brake lights glowing, and steers onto the paved shoulder where it slowly comes to a stop. Close behind it, following the hatchback, a black sedan with two blazing white headlights pulls onto the shoulder and stops a few meters behind it, its headlights lighting the back of the hatchback. Orange sodium streetlights along the road, black lake beyond." + NOPEOPLE),
 "S3": dict(dur=6, refs=[S("grass_field/1"), S("pullover/1")], p=
  "Low locked-off camera at the edge of a field of tall grass at night. Exactly four men in dark suits run from left to right across the frame through the waist-high grass, one behind the other, crisp solid pitch-black silhouettes against two hard white flashlight beams shining from behind them through faint mist. The grass is a dark silhouette mass with only its tops rim-lit. Black sky, a thin row of orange lights on the far horizon. Sharp, no motion blur." + SUIT),
 "S5": dict(dur=6, refs=[S("pullover/2")], p=
  "Low tracking shot from a car speeding along a dark lakefront highway at night, looking sideways at the paved shoulder. Four men in dark suits stand perfectly still in a row on the shoulder, solid pitch-black silhouettes backlit by orange sodium streetlights. The camera rushes past them at high speed, so the four standing men and the streetlight poles slide quickly across the frame from right to left and disappear. Sharp, physical, one continuous moving shot." + SUIT),
}
for k, s in R.items():
    inp = {"prompt": s["p"] + LOOK, "duration": s["dur"], "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": False}
    if "image" in s: inp["image"] = s["image"]
    if "refs" in s: inp["reference_images"] = s["refs"]
    json.dump({"model": "bytedance/seedance-2.5", "tag": f"nj_{k}_t2", "notes": f"non-Jade roto base {k} retake t2", "input": inp},
              open(os.path.join(HERE, f"{k}_t2.json"), "w"), indent=1)
print("ok")
