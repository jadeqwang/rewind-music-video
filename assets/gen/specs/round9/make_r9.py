#!/usr/bin/env python3
"""Round 9 (COPY_v9): J_stopplay, S3_sprint, J_committee. Seedance 2.5 i2v 720p 16:9, no audio."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../anime"); from make_specs import LOOK
D = os.path.dirname(os.path.abspath(__file__))
S3 = json.load(open(D + "/../nonjade/S3_t2.json"))["input"]["prompt"]; S3_LOOK = S3[S3.index("Single continuous shot"):]
SHOTS = {
 "J_stopplay": (5, "assets/character/anime/shots/J_stopplay_720.jpg",
   "Straight-on waist-up shot, plain dark blue-black background, soft cool night light on her, locked-off camera. She looks into "
   "the lens, then firmly raises her right hand and holds it up flat in front of her at shoulder height, PALM FACING THE CAMERA, "
   "fingers together and pointing up - a firm 'STOP' gesture - and holds it perfectly still for about one and a half seconds, "
   "face visible beside the hand. Then she lowers the hand, extends her index finger and taps it forward once toward the camera, "
   "like pressing a PLAY button in the air, and ends with a small knowing smile. Her mouth stays closed (no talking)." + LOOK),
 "S3_sprint": (6, "assets/sets/grass_field/1.jpg",
   "Low camera at the edge of a field of tall grass at night. Four or five men in dark suits and sunglasses come RUNNING AT FULL "
   "SPRINT, not walking - long fast strides, both feet leaving the ground, arms pumping hard, suit coats and ties flying back - "
   "out of the darkness toward the camera through the waist-high grass, and the closest ones rush right past the camera on both "
   "sides. Flashlight beams in their hands swing wildly as they run; two hard white beams behind them through faint mist. They "
   "are solid pitch-black backlit silhouettes, faces completely in shadow and unreadable, only the outlines of sunglasses, "
   "shoulders and arms. Grass whips and splits around their legs. Very fast, urgent, relentless. " + S3_LOOK),
 "J_committee": (5, "assets/character/anime/committee_ff_720.jpg",
   "Dark seminar room, the long committee table with eight copies of the same young woman seated behind it. Subtle motion only: "
   "the one on the far left keeps writing, her pen moving; the arms-crossed one tilts her head slightly; the sleeping one breathes "
   "slowly; the one with glasses turns a page; the snacking one takes a small bite; the knowing one keeps smiling at the camera "
   "and blinks slowly once; the mint-jacket one shifts her chin on her fist. The projector beam stays steady. Very slow, gentle "
   "camera push-in. All eight faces stay the same and keep their positions, no one stands up, no new people appear." + LOOK),
}
if __name__ == "__main__":
    take = sys.argv[1] if len(sys.argv) > 1 else "t1"
    for s, (dur, img, p) in SHOTS.items():
        sp = {"model": "bytedance/seedance-2.5", "tag": f"r9_{s}_{take}", "notes": f"round9 {s} {take} (COPY_v9)",
              "input": {"prompt": p, "image": f"file:{img}", "duration": dur, "resolution": "720p", "aspect_ratio": "16:9",
                        "generate_audio": False, "use_virtual_avatar": False}}
        json.dump(sp, open(f"{D}/{s}_{take}.json", "w"), indent=1); print(f"{D}/{s}_{take}.json")
