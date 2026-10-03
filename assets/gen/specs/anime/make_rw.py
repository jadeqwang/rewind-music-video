#!/usr/bin/env python3
"""R_rw1..4: "Rewind." performance clips (v5 audio clock). Seedance 2.5 i2v 720p, first frame = J5_v3 / J5b_v3 (jacket v3),
reference audio = v5 vocal-stem slice starting 0.3 s before the sung word."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_specs import LOOK
D = os.path.dirname(os.path.abspath(__file__))
STAGE = ("Centre-locked straight-on performance shot in a dark void with red and blue police-siren rim light pulsing; she stands "
         "square to the camera, waist-up, eyes to the lens. Locked-off camera, plain dark void background (no lights, no tubes, no "
         "objects in the background). ")
SING = ("Right at the start she sings the single word \"Rewind\" from the reference audio, in exact sync: lips together softly on "
        "\"re-\", then the mouth opens wide on \"-WIND\" and holds it, then she closes her lips. Her hands never cover her mouth or "
        "face; the face stays fully visible. ")
TWIRL = ("Gesture: she raises her right hand beside her face at shoulder height (to the side, not in front of her mouth) and her "
         "pointing index finger twirls fast small circles in the air COUNTER-CLOCKWISE as seen by the viewer (right, up, left, down, "
         "like turning a clock's hands backwards) - the universal 'rewind' twirl, three or four quick turns - then she pulls the hand "
         "backwards over her shoulder. ")
ROLL = ("Gesture: both forearms held in front of her chest below her chin, both hands rolling around each other BACKWARDS, toward "
        "herself (the top of the roll moves toward her body, the bottom moves out toward the camera) - the reverse of the 'keep "
        "rolling' gesture, a fast continuous rewind roll - then both hands pull back toward her shoulders. ")
SHOTS = {"R_rw1": ("J5", TWIRL, "vocals_v5_rw1_51.546_5.mp3"), "R_rw2": ("J5b", ROLL, "vocals_v5_rw2_55.289_5.mp3"),
         "R_rw3": ("J5", TWIRL, "vocals_v5_rw3_111.652_5.mp3"), "R_rw4": ("J5b", ROLL, "vocals_v5_rw4_115.258_5.mp3")}
if __name__ == "__main__":
    take = sys.argv[1] if len(sys.argv) > 1 else "t1"
    for s, (base, g, aud) in SHOTS.items():
        sp = {"model": "bytedance/seedance-2.5", "tag": f"anime_{s}_{take}", "notes": f"anime Jade {s} {take} rewind gesture+lip, clock v5",
              "input": {"prompt": STAGE + SING + g + LOOK, "image": f"file:assets/character/anime/shots/{base}_v3_720.jpg", "duration": 5,
                        "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": False, "use_virtual_avatar": False,
                        "reference_audios": [f"file:analysis/slices/{aud}"]}}
        fn = f"{D}/{s}_{take}.json"; json.dump(sp, open(fn, "w"), indent=1); print(fn)
