#!/usr/bin/env python3
"""Canonical anime Jade = refs/jade/Pasted image.png, minimal gpt-image-2 edits.
Usage: edit.py JOB[,JOB] [n] [k0]  -> assets/character/anime/cands/<job>_<k>.jpg ; logs prompts.json"""
import sys, os, json, time, threading, io, base64
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; sys.path.insert(0, ROOT + "/tools")
from cf import run_model, save_media
from PIL import Image, ImageOps
OUT = ROOT + "/assets/character/anime"; PJ = OUT + "/prompts.json"; LOCK = threading.Lock()
SRC = {"orig": ROOT + "/refs/jade/Pasted image.png", "canon": OUT + "/CANON_SHEET.jpg",
       "head": OUT + "/CANON_HEAD_front.jpg", "photo29": ROOT + "/refs/jade/image-1790918316346.webp"}

def uri(path, mx=1024, pad=None):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if pad:  # pad to aspect (w/h) with the sheet's own background colour
        w, h = im.size; bg = im.getpixel((3, 3)); W = max(w, round(h * pad)); H = max(h, round(w / pad))
        c = Image.new("RGB", (W, H), bg); c.paste(im, ((W - w) // 2, (H - h) // 2)); im = c
    im.thumbnail((mx, mx)); b = io.BytesIO(); im.save(b, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

KEEP = ("Keep everything else EXACTLY identical to the input image: the same face, the same eyes and their size and shape, "
        "the same hair, line weight, flat cel shading, colours, poses, layout, background and the view labels; keep the "
        "jacket's '1420 MHz' patch, the pale-blue dot patch and the back print exactly as they are. Do not add glasses.")
STYLE_LOCK = ("Draw her EXACTLY as in the reference character sheet (image 1): same anime face, same eyes and eye size, same "
              "center-parted long straight black hair with curtain bangs, same line weight, flat cel shading and palette, "
              "same outfit: white cropped bomber jacket with orange bands, '1420 MHz' patch and pale-blue dot patch, black crop "
              "top, black trousers, white sneakers. No glasses, no headphones, no antenna. ")
JOBS = {
 "S_canon": (["orig"], 1.5, "1536x1024",
   "Edit this official anime character turnaround sheet with three small changes, identical in all four views (front, "
   "three-quarter, side, back): (1) recolour the cargo trousers from navy blue to true BLACK (deep neutral black with dark-gray "
   "cel shading; keep their cut, pockets and orange straps shapes); (2) remove the Yagi antenna prop completely - her hands "
   "simply hang relaxed and empty at her sides; (3) remove the orange headphones from her neck completely, showing her neck and "
   "the black top's collar. " + KEEP),
 "E_expr": (["canon"], None, "1536x1024",
   STYLE_LOCK + "Make an expression sheet of this exact character: 2x2 grid of large head-and-shoulders portraits, slight "
   "three-quarter front view, plain light warm-gray background like the sheet: top-left FOCUSED DRIVING (calm, eyes forward, "
   "slight concentration); top-right STARTLED (eyes a little wider, brows raised, lips parted); bottom-left SINGING SOFTLY "
   "(eyes half-lowered, mouth gently open); bottom-right DETERMINED (brows lowered and set, firm mouth, steady gaze). Eyes keep "
   "the same size and shape as on the sheet in every panel. Small caption under each: FOCUSED, STARTLED, SINGING, DETERMINED."),
 "E_expr2": (["head"], None, "1536x1024",
   "Image 1 is a close-up of the approved anime character (front view, from her official model sheet). Keep her face EXACTLY as "
   "drawn: same face shape, same large eyes with the same size, shape, iris colour and highlights, same nose and mouth placement, "
   "same center-parted long straight black hair with curtain bangs, same thin clean lineart and flat pale cel shading. No glasses, "
   "no headphones. Make an expression sheet: 2x2 grid of LARGE head close-ups (head and neck only, the face filling most of each "
   "panel, slight three-quarter front view, black high-neck top collar visible), plain light warm-gray background: top-left "
   "FOCUSED DRIVING (calm, eyes forward, slight concentration, lips closed); top-right STARTLED (eyes a little wider, brows "
   "raised, lips parted); bottom-left SINGING SOFTLY (eyes softly half-lowered, mouth gently open); bottom-right DETERMINED (brows "
   "lowered and set, firm mouth, steady gaze). The eyes keep the same size and shape as image 1 in every panel (never smaller). "
   "Small caption under each: FOCUSED, STARTLED, SINGING, DETERMINED."),
 "K_drive": (["canon"], None, "1536x1024",
   STYLE_LOCK + "Anime film keyframe, 16:9, same art style as the sheet: night, she drives alone in a white 2001 Acura TL "
   "(second-gen sedan), US left-hand drive: she sits in the LEFT front seat with the steering wheel in front of her; simple "
   "early-2000s dashboard with analog gauges, no touchscreen; the empty passenger seat is on the right. Camera outside the "
   "windshield, front-right three-quarter, looking in at her; her head and shoulders face the same way (forward, down the road), "
   "both hands on the wheel. Chicago Lake Shore Drive city lights streak past in cool blue; the rear-view mirror at the top "
   "centre of the windshield glows with red and blue police lights behind her, tinting the cabin edges red/blue. Her face is "
   "lit softly by the dash glow, clean and calm-focused. No text."),
 "K_perform": (["canon"], None, "1536x1024",
   STYLE_LOCK + "Anime film keyframe, 16:9, same art style as the sheet: centre-locked symmetrical performance shot; she stands "
   "dead centre facing the camera straight-on, square shoulders, waist-up, singing softly with mouth slightly open, eyes to "
   "the lens. Dark near-black void background; strong red police-siren rim light from frame-left and blue rim light from "
   "frame-right outlining her hair, shoulders and jacket; her face lit by a soft even white front fill (no harsh shadows on "
   "the face). Paranoid dream mood like Satoshi Kon's Perfect Blue. No text."),
}

def one(job, k, quality):
    imgs, pad, size, prompt = JOBS[job]
    pl = {"prompt": prompt, "images": [uri(SRC[i], pad=pad) for i in imgs], "size": size, "quality": quality, "output_format": "jpeg"}
    out = f"{OUT}/cands/{job}_{k}"; os.makedirs(OUT + "/cands", exist_ok=True); err = None
    for att in range(4):
        t0 = time.time()
        try:
            r = run_model("openai/gpt-image-2", pl, timeout=90, retries=0, verbose=False)
            paths = save_media(r, out + "_raw"); src = [x for x in paths if not x.endswith(".json")][0]
            Image.open(src).convert("RGB").save(out + ".jpg", quality=93); os.remove(src)
            for x in paths:
                if x.endswith(".json") and os.path.exists(x): os.remove(x)
            err = None; break
        except Exception as e:
            err = str(e)[:160]; print(job, k, "retry", att, err[:80], flush=True)
    rec = {"file": out + ".jpg", "job": job, "model": "openai/gpt-image-2", "quality": quality,
           "refs": [os.path.basename(SRC[i]) for i in imgs], "size": size, "prompt": prompt,
           "secs": round(time.time() - t0, 1), "attempts": att + 1, "est_cost_usd": 0.07 * (att + 1), "error": err}
    with LOCK:
        L = json.load(open(PJ)) if os.path.exists(PJ) else []
        L.append(rec); json.dump(L, open(PJ, "w"), indent=1, ensure_ascii=False)
    print(job, k, rec["secs"], "ERR" if err else "ok", flush=True)

if __name__ == "__main__":
    jobs = sys.argv[1].split(","); n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    k0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0; q = sys.argv[4] if len(sys.argv) > 4 else "medium"
    with ThreadPoolExecutor(4) as ex:
        for jb in jobs:
            for k in range(n): ex.submit(one, jb, k0 + k, q)
