#!/usr/bin/env python3
"""Generate white 2001 Acura TL reference stills. Usage: gen.py VIEW[,VIEW] [n] [model]
Writes analysis/car/cands/<view>_<k>.jpg and logs to assets/car/prompts.json."""
import sys, os, json, time, threading, random
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; sys.path.insert(0, ROOT + "/tools")
from cf import run_model, save_media
from PIL import Image

CAR = ("a white 2001 Acura TL, the second-generation 1999-2003 Acura TL four-door mid-size Japanese luxury sedan: "
       "soft rounded late-1990s body with smooth curved panels and no sharp creases, a gently sloping rounded nose, "
       "slim narrow horizontal wraparound headlights, a small chrome-accented grille with a simple chrome caliper-shaped badge, "
       "short rounded trunk deck, wide horizontal tail lights wrapping around the rear corners, a long greenhouse with six side windows "
       "and thin chrome window trim, body-coloured bumpers, modest 16-inch five-spoke alloy wheels with tall sidewall tyres. "
       "Clean glossy white paint. An authentic early-2000s car, not a modern car")
BG = ("The car is alone, centered with generous margin, isolated on a plain seamless flat dark charcoal-gray studio background "
      "with a faint soft floor shadow, nothing else in the frame. Night lighting: dark low-key studio, hard cold white rim lights "
      "outline the whole body silhouette in crisp highlights, high contrast. ")
TAIL = (" Photographic, sharp focus, product-shot clarity. No text, no lettering, no badges with letters, no license plate "
        "(blank smooth plate area), no watermark, no people.")
VIEWS = {
 "rear34": "Elevated rear three-quarter view from behind and above, like a drone following the car at about 30 degrees above, "
           "looking down at the roof, rear window, trunk lid and the rear-left corner. The red tail lights are glowing.",
 "rear":   "Exactly straight-on rear view at bumper height, perfectly symmetrical, seen from directly behind. "
           "Both wide red tail lights are switched on and glowing bright red, the rear window dark.",
 "side":   "Exact side profile view from the driver's (left) side, car facing left, perfectly orthographic-looking flat side elevation, "
           "camera at door height, the whole length of the car visible. Tail lights glowing red, headlights on.",
 "front34":"Low front three-quarter view from the front-left, headlights switched on and glowing hard white, "
           "showing the slim headlights, the grille and the left flank.",
 "top":    "Exactly top-down overhead view from directly above, looking straight down at the roof, car pointing up toward the top of the frame, "
           "symmetrical plan view showing the hood, windshield, roof, rear window and trunk outline; red tail lights glowing at the bottom, "
           "headlights at the top. The whole car fits in the frame with wide empty margin on all sides, car occupying about 70 percent of the frame height.",
}
PRICE = {"openai/gpt-image-2": 0.06, "xai/grok-imagine-image-quality": 0.05}
LOCK = threading.Lock(); PJ = ROOT + "/assets/car/prompts.json"

def prompt(view): return VIEWS[view] + " The car: " + CAR + ". " + BG + TAIL

def one(view, k, model):
    p = prompt(view)
    pl = ({"prompt": p, "size": "1024x1024" if view == "top" else "1536x1024", "quality": "medium", "output_format": "jpeg"} if model.startswith("openai")
          else {"prompt": p, "aspect_ratio": "1:1" if view == "top" else "16:9", "response_format": "b64_json", "resolution": "1k"})
    out = f"{ROOT}/analysis/car/cands/{view}_{k}"; os.makedirs(os.path.dirname(out), exist_ok=True)
    for att in range(3):
        t0 = time.time()
        try:
            r = run_model(model, pl, timeout=60, retries=0, verbose=False)
            paths = save_media(r, out + "_raw"); src = [x for x in paths if not x.endswith(".json")][0]
            im = Image.open(src).convert("RGB"); w, h = im.size
            if view != "top" and abs(w / h - 16 / 9) > 0.02:
                nh = round(w * 9 / 16); t = (h - nh) // 2; im = im.crop((0, t, w, t + nh))
            im.save(out + ".jpg", quality=93); os.remove(src)
            for x in paths:
                if x.endswith(".json") and os.path.exists(x): os.remove(x)
            err = None; break
        except Exception as e:
            err = str(e)[:200]
    rec = {"file": out + ".jpg", "view": view, "model": model, "prompt": p, "secs": round(time.time() - t0, 1),
           "cost": PRICE.get(model, 0.06) * (att + 1), "error": err}
    with LOCK:
        L = json.load(open(PJ)) if os.path.exists(PJ) else []
        L.append(rec); json.dump(L, open(PJ, "w"), indent=1)
    print(view, k, model, rec["secs"], err, flush=True)

if __name__ == "__main__":
    views = sys.argv[1].split(","); n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    model = sys.argv[3] if len(sys.argv) > 3 else "openai/gpt-image-2"; k0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    with ThreadPoolExecutor(4) as ex:
        for v in views:
            for k in range(n): ex.submit(one, v, k0 + k, model)
