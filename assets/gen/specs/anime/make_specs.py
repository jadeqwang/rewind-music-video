#!/usr/bin/env python3
"""Anime Jade shot specs (Seedance 2.5 i2v, 720p 16:9, first frame = assets/character/anime/shots/<SHOT>_720.jpg)."""
import json, sys, os
D = os.path.dirname(os.path.abspath(__file__))
LOOK = (" Anime style, consistent with the first frame, clean cel shading, same character design: same face, same large eyes "
        "(same size, never smaller), same long straight black hair, same white cropped jacket with orange bands and patches, "
        "black top and trousers; no glasses. Smooth, stable lineart, no morphing, correct hands with five fingers. Single "
        "continuous shot, no cuts. No text, no subtitles, no logos.")
LIP = (" She sings the vocal in the reference audio: her lips move in exact sync with each sung word, small natural breaths.")
S = {
 "J1": (8, "vocals_anime_J1_13.85_8.mp3", "Night, she drives the car, seen from the passenger-side dashboard; both hands on the "
        "wheel, eyes on the road ahead, calm and focused. Warm orange sodium streetlight bands slide across her and the cabin "
        "as the car moves; city lights drift past behind her. Camera stays locked to the car." + LIP),
 "J2": (4, None, "Night, she drives; while the car moves, her eyes flick up to the rear-view mirror and hold there with faint "
        "unease, then a tiny swallow; her head barely moves. Warm streetlight bands slide across the cabin. Camera locked to the car."),
 "J3": (6, None, "Night, the car is stopped at the roadside under pulsing red and blue police lights from behind. She slowly "
        "reaches out and holds her driver's license card up at the open window toward someone standing just off-frame right, "
        "her arm steady, her face calm and compliant, eyes looking up at him. The red and blue light pulses rhythmically over "
        "her hair and the car. Locked-off camera."),
 "J5": (7, None, "Centre-locked straight-on performance shot in a dark void with red and blue siren rim light pulsing. She "
        "slowly raises her right hand in front of her chest and draws one big slow counter-clockwise circle in the air with "
        "her index finger, like rewinding time, then lowers it; her body stays square to the camera, eyes to the lens, lips "
        "slightly parted. Locked-off camera."),
 "J5b": (7, None, "Centre-locked straight-on performance shot in a dark void with blue and red siren rim light pulsing. Her "
        "raised open hand sweeps slowly backwards past her shoulder, as if scrubbing time back, while her long hair drifts "
        "and flows sideways in a slow wind; body square to the camera, eyes to the lens. Locked-off camera."),
 "J6": (8, "vocals_anime_J6_73.2_8.mp3", "Night, she drives, seen through the windshield from the front, both hands firm on "
        "the wheel, determined steady gaze down the road; red and blue police light pulses in the rear-view mirror; city "
        "lights stream past. Camera locked to the car." + LIP),
 "J7w": (7, None, "Wide night shot: she sprints through the field of tall grass from left to right, legs and arms pumping, hair "
        "streaming; the camera pans slowly to follow her. Two hard white flashlight beams sweep across the grass from behind "
        "her, and the grass whips in the wind."),
 "J7m": (6, None, "Medium tracking shot at night: she runs away through the tall grass, glances back over her left shoulder "
        "toward the camera with wide alert eyes, then turns forward again and keeps running; hair flying; white flashlight "
        "beams flare across the grass behind her. The camera tracks with her."),
 "J8": (8, "vocals_anime_J8_147.47_8.mp3", "Dark empty seminar room: she sits alone on the single chair, hands resting on her "
        "knees, and sings softly toward the camera, eyes softly lowered, very little body motion. The projector beam stays "
        "steady; faint red and blue glow from the window. Slow, gentle push-in." + LIP),
 "J8b": (6, None, "Dark seminar room, seen from behind her chair: she slowly turns around in the chair, head and shoulders "
        "rotating together over her right shoulder, to look straight back at the camera with wide eyes. The projector beam "
        "stays steady. Locked-off camera."),
 "J9": (8, None, "Night, final-act energy: she drives fast and steady, both hands firm on the wheel, eyes locked on the road, "
        "not slowing down. Wind from the open window whips her long hair back and sideways; orange sodium streetlights strobe "
        "across her and the cabin in a fast rhythm; red and blue police lights blaze in the rear-view mirror. Camera locked "
        "to the car."),
 "Jeyes": (5, None, "Extreme close-up of her eyes, wide awake and unblinking: reflections of orange and red/blue light trails "
        "slide smoothly across her irises and the glossy eye surface from one side to the other; a faint rhythmic heartbeat "
        "tremor. Locked-off camera, eyes stay exactly the same size."),
}
def spec(shot, take="t1", extra_note="", **over):
    dur, aud, p = S[shot]
    inp = {"prompt": p + LOOK, "image": f"file:assets/character/anime/shots/{shot}_720.jpg", "duration": dur,
           "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": False, "use_virtual_avatar": False}
    if aud: inp["reference_audios"] = [f"file:analysis/slices/{aud}"]
    inp.update(over)
    sp = {"model": "bytedance/seedance-2.5", "tag": f"anime_{shot}_{take}", "notes": f"anime Jade {shot} {take} {extra_note}".strip(), "input": inp}
    fn = f"{D}/{shot}_{take}.json"; json.dump(sp, open(fn, "w"), indent=1); return fn
if __name__ == "__main__":
    for s in (sys.argv[1:] or S): print(spec(s))
