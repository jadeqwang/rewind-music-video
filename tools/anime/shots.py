#!/usr/bin/env python3
"""Anime first frames for the Jade shots (gpt-image-2 single-input edits; one input image keeps it under the ~30 s proxy cut).
Scene shots use a single composite reference board (model sheet + face close-up + set plate) as the one input image.
Usage: shots.py JOB[,JOB] [n] [k0] [quality]  -> assets/character/anime/shots/cands/<job>_<k>.jpg (1536x1024 raw)
       shots.py crop CAND OUT [y0]           -> 16:9 crop 1536x864 (y0 default centred) + 1280x720 copy
Log: assets/character/anime/shots/prompts.json"""
import sys, os, json, time, threading, io, base64
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; sys.path.insert(0, ROOT + "/tools")
from cf import run_model, save_media
from PIL import Image, ImageOps
A = ROOT + "/assets/character/anime"; OUT = A + "/shots"; PJ = OUT + "/prompts.json"; LOCK = threading.Lock()
SHEET, HEAD_F, HEAD_34 = A + "/CANON_SHEET.jpg", A + "/CANON_HEAD_front.jpg", A + "/CANON_HEAD_34.jpg"
KDRIVE, KPERF = A + "/cands/K_drive_1.jpg", A + "/cands/K_perform_0.jpg"
SETS = ROOT + "/assets/sets"

def board(plate, head=HEAD_34):
    """1536x1024: left = sheet front+3/4 figures, right-top = face close-up, right-bottom = set plate."""
    c = Image.new("RGB", (1536, 1024), (240, 240, 238))
    sh = Image.open(SHEET).convert("RGB").crop((0, 0, 768, 1024)); c.paste(sh, (0, 0))
    hd = Image.open(head).convert("RGB").resize((448, 448)); c.paste(hd, (768 + 160, 20))
    pl = Image.open(plate).convert("RGB"); pl = pl.resize((768, round(768 * pl.height / pl.width)))
    c.paste(pl, (768, 1024 - pl.height - 20)); return c

def uri(src, mx=1024):
    im = src if isinstance(src, Image.Image) else ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im = im.copy(); im.thumbnail((mx, mx)); b = io.BytesIO(); im.save(b, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

CHAR = ("same anime face as the model sheet: large dark-brown eyes with the SAME size, shape and highlights (never smaller), soft "
        "thin brows, small nose, heart-shaped face, long straight black center-parted hair with curtain bangs falling past the "
        "shoulders; same outfit: white cropped bomber jacket with orange horizontal bands on chest and sleeves, round '1420 MHz' "
        "patch ONLY on her LEFT upper sleeve (her right sleeve has NO patch), pale-blue dot patch on her LEFT chest, black high-neck crop top, black cargo trousers, "
        "white sneakers. No glasses, no headphones, no antenna. ")
STYLE = ("Same art style as the sheet: clean thin confident lineart, flat cel shading with 2-3 tones, premium anime feature film "
         "(Satoshi Kon / Makoto Shinkai). Night lighting, but her face is lit by a soft, even, gentle fill (clean, youthful, no "
         "harsh shadows on the face) with a coloured rim light on hair and shoulders. Full-bleed single frame, 16:9 cinematic "
         "composition: keep her head and hands inside the central horizontal band (top and bottom 8% of the canvas may be "
         "cropped). No text, no captions, no panels, no borders. ")
BOARD = ("The input is a reference board: LEFT = the official model sheet of the character (front and three-quarter view), "
         "TOP-RIGHT = her face close-up, BOTTOM-RIGHT = a photo of the location. Draw ONE new anime film frame (not a board) "
         "of this exact character in that location, the location redrawn in the same anime style. ")
CAR = ("Keep the art style, her face (same eyes, same size), hair, outfit and patches exactly as in the input image. The car is a "
       "white 2001 Acura TL, US LEFT-HAND DRIVE: she sits in the LEFT front seat behind the steering wheel; simple early-2000s "
       "dashboard with analog gauges, no touchscreen. The round '1420 MHz' patch is ONLY on her LEFT sleeve; her RIGHT sleeve is plain white with the orange band (no patch). ")

FIX = ("Edit this anime film frame minimally: remove the round '1420 MHz' patch from her RIGHT sleeve, so that sleeve is plain "
       "white with only the orange band. Keep EVERYTHING else exactly identical: face, eyes and their size, hair, pose, lighting, "
       "background, composition, line weight and colours. ")
JOBS = {
 "J9fix": (OUT + "/cands/J9_1.jpg", FIX),
 "J3fix": (OUT + "/cands/J3_1.jpg", "Edit this anime film frame minimally: remove the police car and its light bar at the top-left "
   "(replace with dark night road and distant city lights). The red and blue police light now comes from BEHIND her car "
   "(frame-right, beyond the rear door), washing red/blue over the rear of the car, her hair rim and the dark figure at the right "
   "edge. Keep EVERYTHING else exactly identical: her face, eyes and their size, hair, pose, the blank ID card, car, composition, "
   "line weight and colours. "),
 "J1fix": (OUT + "/cands/J1_0.jpg", FIX), "J2fix": (OUT + "/cands/J2_0.jpg", FIX),
 # --- car shots (single input: approved K_drive_1 keyframe) ---
 "J1": (KDRIVE, "Edit this anime film frame. " + CAR + "New camera: mounted on the passenger-side dashboard looking back-left "
   "at her, so we see her in three-quarter front view from her right side, head and shoulders and both hands on the wheel, "
   "the driver's window and the dark lakefront road behind her. No police lights yet: the rear-view mirror is dark. Warm "
   "orange sodium streetlight bands slide across the cabin. She is singing softly, lips slightly parted, calm eyes on the "
   "road ahead (looking toward frame-right, forward through the windshield); head and shoulders face the same way. " + STYLE),
 "J2": (KDRIVE, "Edit this anime film frame. " + CAR + "New camera: close medium shot from the passenger seat at her head height, "
   "her face in three-quarter front view from her right, the rear-view mirror at the top of the frame near her; the mirror "
   "shows only a faint dim pair of headlights far behind (no police lights). Her eyes glance up toward the rear-view mirror "
   "with faint unease, lips closed, brows very slightly raised; head mostly forward, shoulders forward. Warm sodium light "
   "bands. " + STYLE),
 "J3": (KDRIVE, "Edit this anime film frame. " + CAR + "New scene: the car is stopped on the road shoulder at night. Camera "
   "outside the car next to the open driver's window (her LEFT side), at window height, medium shot: the window is rolled "
   "fully down, she sits in the driver's seat turned slightly toward the camera and holds up her driver's license card in her "
   "left hand at the window opening: a plain horizontal ID card with a blank face (no readable text). Her other hand rests on "
   "the wheel. Strong red and blue police light floods from behind the car (frame-left/back), rimming her hair and the car "
   "door; her face stays softly, evenly lit. Calm compliant expression, lips closed, eyes looking up at someone standing "
   "just off-frame right. " + STYLE),
 "J6": (KDRIVE, "Edit this anime film frame minimally. Keep the camera, composition, car, cabin, skyline and her pose exactly. "
   + CAR + "Change only: her expression becomes DETERMINED (brows slightly lowered and set, steady gaze forward), lips "
   "parted as if singing a word; the red/blue police glow in the rear-view mirror stays. Keep her eyes exactly the same size "
   "and shape. " + STYLE),
 "J9": (KDRIVE, "Edit this anime film frame. " + CAR + "New camera: from the passenger seat, medium close-up of her in "
   "three-quarter front view from her right, the driver's window behind her is rolled DOWN and a strong draft whips her long "
   "black hair back and sideways. The rear-view mirror at the top of the frame blazes with red and blue police lights. Warm "
   "orange sodium streetlight light streaks across her and the cabin. Steady, determined expression, eyes forward on the road, "
   "lips closed, both hands firmly on the wheel; head and shoulders face forward together. High-energy final-act mood. " + STYLE),
 # --- performance ---
 "J5b": (KPERF, "Edit this anime film frame. Keep her face (same eyes, same size), hair, outfit, patches, dark void and siren rim "
   "lighting style exactly. New framing: slightly wider, waist-up, centre-locked, straight-on, square shoulders. Swap the rim "
   "colours: blue rim from frame-left, red rim from frame-right. Her long hair is lifted and drifting sideways in a wind. Her "
   "right hand is raised in front of her chest, palm open and facing sideways, about to sweep backwards; the left hand relaxed "
   "at her side. Lips slightly parted. " + STYLE),
 # --- scene shots (single composite reference board) ---
 "J7w": (("board", SETS + "/grass_field/1.jpg", HEAD_34), BOARD + CHAR + "WIDE shot at night: she runs alone through a vast "
   "field of tall waist-high grass toward frame-right, full body small in the frame (about one third of the frame height), "
   "mid-stride, arms pumping, hands empty, long hair streaming behind her. Two hard white flashlight beams rake across the "
   "grass from behind her (frame-left, far back), the distant orange city skyline line on the horizon. Grass is dark "
   "silhouette with rim-lit tops. Her face in profile-three-quarter, softly lit. " + STYLE),
 "J7m": (("board", SETS + "/grass_field/1.jpg", HEAD_34), BOARD + CHAR + "MEDIUM shot at night (waist-up), tracking camera slightly "
   "BEHIND her and to her left: she runs AWAY from the camera through tall grass toward the frame-right background, and "
   "twists to look back over her LEFT shoulder at the camera (at her pursuers) with wide alert eyes, lips slightly parted; her "
   "upper body twists with her head (congruent), we see her left side and part of her back, hair flying. Hard white "
   "flashlight beams from behind her flare across the grass and rim her hair. Hands empty. " + STYLE),
 "J8": (("board", SETS + "/defense_room/1.jpg", HEAD_F), BOARD + CHAR + "Inside the dark university seminar room: she sits "
   "alone on the single chair in the middle of the floor, seen from the front at a slight angle (camera low, in front of her, "
   "the long committee table with five empty chairs behind her, blank chalkboard, the projector beam cutting through the dark "
   "from frame-left). Medium-wide, she sits upright, hands resting on her knees, face toward the camera, singing softly with "
   "lips gently open, eyes softly lowered. Cold white projector light rims her from the side; faint red and blue glow from the "
   "window. " + STYLE),
 "J8b": (("board", SETS + "/defense_room/1.jpg", HEAD_34), BOARD + CHAR + "Inside the dark university seminar room, seen from "
   "BEHIND the single chair: she sits on the lone chair in the middle of the floor facing the long committee table with five "
   "empty chairs and the blank chalkboard; the projector beam cuts across from frame-left. Medium shot from behind and slightly "
   "to her right: we see her back (the big pale-blue circle back print on the jacket) and long hair, and she is beginning to "
   "turn her head and shoulders back toward the camera over her right shoulder, face in three-quarter view, eyes wide, lips "
   "closed. " + STYLE),
 "Jeyes": (HEAD_F, "Edit this anime character close-up into an EXTREME close-up film frame of her EYES: crop from just above "
   "the brows to the nose bridge, both eyes filling the width of the frame, exactly the same eye shape, size, iris colour and "
   "highlights as the input (never narrower), same thin lineart and flat cel shading. Night inside a car: dark surroundings, "
   "soft even light on the skin; in each iris and on the glossy eye surface the reflections of orange and red/blue streaking "
   "light trails. Wide-awake, tense, unblinking stare straight ahead. " + STYLE),
}

def one(job, k, quality):
    src, prompt = JOBS[job]
    img = board(src[1], src[2]) if isinstance(src, tuple) else src
    pl = {"prompt": prompt, "images": [uri(img)], "size": "1536x1024", "quality": quality, "output_format": "jpeg"}
    out = f"{OUT}/cands/{job}_{k}"; os.makedirs(OUT + "/cands", exist_ok=True); err = None
    for att in range(4):
        t0 = time.time()
        try:
            r = run_model("openai/gpt-image-2", pl, timeout=90, retries=0, verbose=False)
            paths = save_media(r, out + "_raw"); s = [x for x in paths if not x.endswith(".json")][0]
            Image.open(s).convert("RGB").save(out + ".jpg", quality=94); os.remove(s)
            for x in paths:
                if x.endswith(".json") and os.path.exists(x): os.remove(x)
            err = None; break
        except Exception as e:
            err = str(e)[:160]; print(job, k, "retry", att, err[:80], flush=True)
    rec = {"file": out + ".jpg", "job": job, "model": "openai/gpt-image-2", "quality": quality,
           "src": "board:" + os.path.basename(src[1]) if isinstance(src, tuple) else os.path.basename(src),
           "prompt": prompt, "secs": round(time.time() - t0, 1), "attempts": att + 1, "est_cost_usd": 0.07 * (att + 1), "error": err}
    with LOCK:
        L = json.load(open(PJ)) if os.path.exists(PJ) else []
        L.append(rec); json.dump(L, open(PJ, "w"), indent=1, ensure_ascii=False)
    print(job, k, rec["secs"], "ERR" if err else "ok", flush=True)

def crop(cand, out, y0=None):
    im = Image.open(cand).convert("RGB").resize((1536, 1024)); y0 = 80 if y0 is None else int(y0)
    c = im.crop((0, y0, 1536, y0 + 864)); c.save(out, quality=95)
    c.resize((1280, 720), Image.LANCZOS).save(out.replace(".jpg", "_720.jpg"), quality=95)

if __name__ == "__main__":
    if sys.argv[1] == "crop":
        crop(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None); sys.exit()
    if sys.argv[1] == "board":
        board(SETS + "/" + sys.argv[2]).save(sys.argv[3]); sys.exit()
    jobs = sys.argv[1].split(","); n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    k0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0; q = sys.argv[4] if len(sys.argv) > 4 else "medium"
    with ThreadPoolExecutor(4) as ex:
        for jb in jobs:
            for k in range(n): ex.submit(one, jb, k0 + k, q)
