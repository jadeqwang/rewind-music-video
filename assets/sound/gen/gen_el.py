import sys, json; sys.path.insert(0, "tools")
from cf import run_model, save_media
P = {
 "rw_a": "Sound effect only, no music, no melody, no drums: a VHS cassette tape being rewound at high speed inside a VCR, mechanical tape transport motor whir rising in pitch, squealing high-speed garbled reversed audio chatter, plastic reel spinning, accelerating for 4 seconds, dry close mic.",
 "rw_b": "Isolated foley, no musical instruments: analog reel-to-reel tape fast rewind, chipmunk-speed reversed voices and music fragments flickering, motor hum and capstan whine ramping up, gritty magnetic tape hiss, cinematic sci-fi time rewind effect.",
 "tick_a": "Isolated sound effect, no music: a single frozen-time suspended moment, a soft reversed reverb swell into one quiet clock tick, airy, eerie, sub-bass hush, cinematic time freeze.",
}
for k, p in P.items():
    ms = 3000 if k.startswith("tick") else 5000
    r = run_model("elevenlabs/music-v2", {"prompt": p, "music_length_ms": ms, "force_instrumental": True})
    print(k, save_media(r, f"assets/sound/gen/{k}"))
