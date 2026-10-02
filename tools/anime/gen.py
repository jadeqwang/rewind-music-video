#!/usr/bin/env python3
"""Anime Jade generator. Usage: gen.py JOB[,JOB] [n] [k0]   (jobs defined in JOBS)
Writes assets/character/anime/cands/<job>_<k>.jpg, logs assets/character/anime/prompts.json."""
import sys, os, json, time, threading, io, base64
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; sys.path.insert(0, ROOT + "/tools")
from cf import run_model, save_media
from PIL import Image, ImageOps
OUT = ROOT + "/assets/character/anime"; PJ = OUT + "/prompts.json"; LOCK = threading.Lock()
RJ = ROOT + "/refs/jade/"
PRICE = {"openai/gpt-image-2": 0.07, "xai/grok-imagine-image-quality": 0.05}

def uri(path, mx=768):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); im.thumbnail((mx, mx))
    b = io.BytesIO(); im.save(b, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

PH = {k: RJ + v for k, v in dict(
    f1="PXL_20260528_215628802.jpg", f2="IMG_20180610_074732_mr1528617091925.jpg", f3="PXL_20250908_195405539.MP.jpg",
    f4="IMG_20160827_121631.jpg", f5="IMG_20180209_082832.jpg", prof="PXL_20260929_003030232.jpg",
    tr1="jade_trace_base.jpg", tr2="jade_trace_jacket_hp_2.jpg", outfit="Pasted image.png").items()}

STYLE = ("Modern premium anime feature-film character design, in the spirit of Satoshi Kon (Paprika, Perfect Blue) "
         "crossed with Makoto Shinkai: clean confident thin lineart, flat cel shading with only 2-3 tones per colour, "
         "subtle soft rim highlights, restrained realistic adult proportions. An adult woman about 27 years old, NOT chibi, "
         "NOT moe, not a generic anime girl: a specific, recognisable person drawn in anime style.")
FACE = ("Her likeness must be unmistakable: heart-shaped 'melon-seed' face (wide temples and high wide cheekbones, the lower "
        "cheeks tapering to a narrow, softly pointed chin, not round, not square, not long); a LARGE, tall, broad forehead and a "
        "proportionally large upper head/cranium; long straight solid black hair with a center part, styled half-up half-down: "
        "two symmetrical sections from left and right of the center part gathered back toward the crown (visible as volume at "
        "the crown in 3/4, profile and back views), the rest hanging long and straight well past the shoulders, a few fine "
        "loose strands at the temples; thin rectangular dark gray-teal metal-frame glasses ALWAYS on, in every view; dark brown "
        "round-almond eyes with a slight thin double-eyelid crease (eyes as large as in her photos or a little larger, never "
        "smaller or narrowed); fuller warm dark-brown natural brows that are NOT mirror images: the brow on the viewer's left "
        "sits slightly lower and flatter, the brow on the viewer's right is slightly higher with its peak further out toward the "
        "tail; small soft nose, natural full lips; a calm, neutral 'resting oblivious' expression. Smooth clear skin, youthful, "
        "soft even frontal light on the face, warm natural skin tone.")
SHEET = ("Character model sheet, 2x2 grid of head-and-shoulders portraits of the SAME woman on a plain light warm-gray "
         "background, each head large in its cell, same scale and same eye height: top-left exact front view; top-right "
         "three-quarter view facing the viewer's left; bottom-left three-quarter view facing the viewer's right; bottom-right "
         "clean side profile facing the viewer's left. She wears a black crew-neck top. No text, no labels, no logos.")
OUTFIT = ("Canonical outfit: a white cropped zip-up jacket (waist length, slightly boxy, collar) with two horizontal orange "
          "bands across the chest and around both sleeves, plain, no patches, no text, no logos; a black fitted top underneath; "
          "plain BLACK straight-leg trousers (black, not navy, no straps); white chunky sneakers.")
TAIL = " No text, no captions, no watermark."

def J(model, imgs, prompt, size="1536x1024"):
    return dict(model=model, imgs=imgs, prompt=prompt, size=size)

G = "openai/gpt-image-2"
JOBS = {
 # --- face-sheet candidates (strategies) ---
 "A_photos": J(G, ["f1", "f2", "f3", "f4", "outfit"],
   "Images 1-4 are real photos of one woman (Jade). Image 5 is ONLY an anime style reference (line quality and colouring; "
   "ignore its face). Redraw Jade as an anime character: preserve HER exact face geometry from the photos - the face outline, "
   "proportions of forehead to face, eye spacing, nose and mouth placement - translated into clean anime line and cel colour. "
   + STYLE + " " + FACE + " " + SHEET + TAIL),
 "B_traces": J(G, ["tr2", "tr1", "f1", "f3"],
   "Images 1-2 are approved stylised drawings of this woman (Jade) that already capture her likeness well; images 3-4 are her "
   "real photos. Convert her into a full-colour anime character, keeping exactly the face shape, proportions, glasses and hair of "
   "the drawings and photos. " + STYLE + " " + FACE + " " + SHEET + TAIL),
 "C_geomlock": J(G, ["f1"],
   "This is a real photo of Jade. Create an anime character sheet of HER. The front view must be a faithful anime tracing of "
   "this exact photo's face: same face outline, same wide forehead and upper head, same jaw and pointed chin, same eye shape "
   "and spacing, same glasses shape, same brows - simplified to clean anime lines and flat cel colour, eyes only slightly "
   "enlarged. " + STYLE + " " + FACE + " " + SHEET + TAIL),
 "D_grok": J("xai/grok-imagine-image-quality", ["f1", "f2", "f3", "tr2"],
   "Anime redraw of the woman in the reference photos (Jade), keeping her exact face shape and features. " + STYLE + " " + FACE
   + " " + SHEET + TAIL),
}
def add_best(best):
    """Jobs that use the chosen sheet (assets/character/anime/best_sheet.jpg) as identity ref."""
    B = OUT + "/best_sheet.jpg"; PH["best"] = B
    base = ("Image 1 is the approved anime character sheet of Jade; keep her EXACTLY as drawn there (same face shape, large "
            "forehead/upper head, glasses, brows, half-up hair, same anime style); image 2 is a real photo of her for likeness. ")
    EX = ("Expression sheet, 2x3 grid of head-and-shoulders portraits of the same woman, slight 3/4 front view, plain light gray "
          "background, black top, glasses on in every panel: (1) focused driving - calm, eyes forward, slight concentration; "
          "(2) startled - eyes a little wider, brows up, lips parted; (3) singing softly - eyes half-lowered, mouth gently open "
          "small 'oo'; (4) determined - brows lowered and set, jaw firm, steady gaze; (5) singing an open 'ah' - mouth open wide, "
          "eyes soft; (6) calm resting oblivious face. Eyes never shrink between panels. ")
    TA = ("Full-body character turnaround, four views side by side on a plain light gray background, same scale, standing "
          "neutral A-pose-ish relaxed stance: FRONT, THREE-QUARTER (turned toward viewer's left), SIDE profile (facing left), "
          "BACK (showing the half-up two-section hair gathered at the crown and the long straight hair). Natural adult "
          "proportions, about 7.5 heads tall. Glasses on in every front/side view. " + OUTFIT + " Image 3 is the OUTFIT and "
          "turnaround layout reference only (but trousers must be plain black, no patches, no orange straps, no antenna prop). ")
    K1 = ("Anime film keyframe, 16:9: night, Jade driving alone inside her white 2001 Acura TL, US left-hand-drive: she sits on the "
          "LEFT side of the car, steering wheel in front of her on the left, simple early-2000s dashboard with analog gauges, no "
          "touchscreen. Camera through the windshield from the front passenger side, slight 3/4, her face and body turned the "
          "same way (toward frame right, looking ahead at the road). Lake Shore Drive city lights streaking, cool blue night; "
          "the rear-view mirror shows red-and-blue police light flashes behind her, tinting the cabin edges. Her face lit softly "
          "by the instrument glow, clean and calm-focused. Wearing the white cropped jacket with orange bands over a black top. ")
    K2 = ("Anime film keyframe, 16:9: centre-locked symmetrical performance shot, Jade standing dead centre facing the camera "
          "straight-on, square shoulders, singing softly, mouth slightly open, eyes toward the lens; dark void background with "
          "strong red and blue police-siren RIM LIGHT outlining her hair and shoulders from both sides, face lit by a soft even "
          "white front fill (no harsh shadows on the face). Mid-shot from the waist up. Wearing the white cropped jacket with "
          "orange bands over a black top. Satoshi Kon dream-paranoia mood. ")
    for k, (p, imgs, size) in {"E_expr": (EX, ["best", "f1"], "1536x1024"), "T_turn": (TA, ["best", "f1", "outfit"], "1536x1024"),
                               "K_drive": (K1, ["best", "f1"], "1536x1024"), "K_perform": (K2, ["best", "f1"], "1536x1024")}.items():
        JOBS[k] = J(G, imgs, base + p + " " + STYLE + " " + FACE + TAIL, size)

def one(job, k):
    j = JOBS[job]; m = j["model"]
    if m.startswith("openai"):
        pl = {"prompt": j["prompt"], "images": [uri(PH[i]) for i in j["imgs"]], "size": j["size"], "quality": "medium", "output_format": "jpeg"}
    else:
        pl = {"prompt": j["prompt"][:3900], "images": [{"url": uri(PH[i])} for i in j["imgs"]], "aspect_ratio": "3:2", "response_format": "b64_json", "resolution": "2k"}
    out = f"{OUT}/cands/{job}_{k}"; os.makedirs(OUT + "/cands", exist_ok=True); err = None; att = 0
    for att in range(4):
        t0 = time.time()
        try:
            r = run_model(m, pl, timeout=90, retries=0, verbose=False)
            paths = save_media(r, out + "_raw"); src = [x for x in paths if not x.endswith(".json")][0]
            Image.open(src).convert("RGB").save(out + ".jpg", quality=93); os.remove(src)
            for x in paths:
                if x.endswith(".json") and os.path.exists(x): os.remove(x)
            err = None; break
        except Exception as e:
            err = str(e)[:200]; print(job, k, "retry", att, err[:100], flush=True)
    rec = {"file": out + ".jpg", "job": job, "model": m, "refs": [os.path.basename(PH[i]) for i in j["imgs"]], "size": j["size"],
           "prompt": j["prompt"], "secs": round(time.time() - t0, 1), "attempts": att + 1, "est_cost": PRICE.get(m, 0.07) * (att + 1), "error": err}
    with LOCK:
        L = json.load(open(PJ)) if os.path.exists(PJ) else []
        L.append(rec); json.dump(L, open(PJ, "w"), indent=1, ensure_ascii=False)
    print(job, k, rec["secs"], "ERR " + err if err else "ok", flush=True)

if __name__ == "__main__":
    jobs = sys.argv[1].split(","); n = int(sys.argv[2]) if len(sys.argv) > 2 else 1; k0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    if any(x[0] in "ETK" for x in jobs): add_best(None)
    with ThreadPoolExecutor(4) as ex:
        for jb in jobs:
            for k in range(n): ex.submit(one, jb, k0 + k)
