#!/usr/bin/env python3
"""Continuity retakes (user notes 2026-10-02): her car = WHITE 2001 ACURA TL (2nd-gen, 4-door, rounded body, slim horizontal
headlights); US left-hand drive, right-hand traffic, heading north on LSD the lake is on the driver's right."""
import json, os
from make_specs import LOOK, NOPEOPLE, S, HERE
CAR = ("a white 2001 Acura TL, a rounded early-2000s four-door mid-size Japanese sedan with slim horizontal headlights and a smooth "
       "simple body, its white paint catching the orange streetlight")
R = {
 "E1_t2": dict(dur=10, refs=[S("lake_shore_drive/2"), S("lake_shore_drive/4")], p=
  f"High aerial drone shot at night above Lake Shore Drive, Chicago, looking north along the long smooth curve of the empty lakefront highway toward the small distant skyline. A single lone car, {CAR}, drives away from the camera, north along the curve in the lanes nearest the lake, its red tail lights and white headlight beams sweeping ahead. The flat pitch-black lake fills the right side of the frame; a dotted line of orange sodium streetlights traces the curve. The drone glides slowly forward, following the car from behind and above, keeping it in the lower middle of the frame." + NOPEOPLE),
 "Epull_t3": dict(dur=4, refs=[S("pullover/3"), S("lake_shore_drive/3")], p=
  f"High wide shot from beside a dark lakefront highway at night, steady camera. {CAR[0].upper() + CAR[1:]}, drives along the highway from right to left, brakes with its red brake lights glowing, and steers onto the paved shoulder where it slowly comes to a stop. Close behind it, following the white sedan, a black sedan with two blazing white headlights pulls onto the shoulder and stops a few meters behind it, its headlights lighting the back of the white car. Orange sodium streetlights along the road, the black lake beyond." + NOPEOPLE),
}
for k, s in R.items():
    inp = {"prompt": s["p"] + LOOK, "duration": s["dur"], "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": False,
           "reference_images": s["refs"]}
    json.dump({"model": "bytedance/seedance-2.5", "tag": f"nj_{k}", "notes": f"continuity retake {k}: white 2001 Acura TL, northbound", "input": inp},
              open(os.path.join(HERE, f"{k}.json"), "w"), indent=1)
print("ok")
