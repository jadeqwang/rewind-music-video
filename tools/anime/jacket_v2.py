#!/usr/bin/env python3
"""Jacket v2 (user, 2026-10-02): snap-tab BAND COLLAR + snap EPAULETTES (Wild Fable mini cropped racer jacket), everything else unchanged.
gpt-image-2 single-input edits. Usage:
  jacket_v2.py sheet N K0 [quality]          -> assets/character/anime/v2/cands/sheet_<k>.jpg  (input CANON_SHEET.jpg)
  jacket_v2.py shot SHOT[,SHOT] N K0 [q]     -> assets/character/anime/v2/cands/<SHOT>_<k>.jpg (input shots/<SHOT>.jpg 1536x864)
Log: assets/character/anime/v2/prompts.json"""
import sys, os, json, time, threading, io, base64
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; sys.path.insert(0, ROOT + "/tools")
from cf import run_model, save_media
from PIL import Image
A = ROOT + "/assets/character/anime"; OUT = A + "/v2"; PJ = OUT + "/prompts.json"; LOCK = threading.Lock()

JACKET = ("Change ONLY the jacket's neckline and shoulders to a moto/racer jacket construction: "
  "(1) COLLAR: replace the collarless neckline with a short STAND-UP BAND COLLAR (racer collar), about 3 cm tall, made of white "
  "vertical-RIBBED knit (fine parallel vertical rib lines), hugging the base of the neck all the way around and standing upright, over "
  "the black high-neck top; at the front opening, on one end of the band collar there is a small horizontal SNAP TAB (a short white "
  "strap tab with one round metal snap button) at the throat; the collar sits on top of a smooth plain front zipper (thin zip tape "
  "lines down both front edges; the jacket stays OPEN/unzipped exactly as now, showing the black crop top). "
  "(2) SHOULDERS: add a structured EPAULETTE on top of EACH shoulder: a flat white fabric strap about 3 cm wide running along the top "
  "of the shoulder from the collar seam out to the shoulder point, outlined with a clean line and fastened with one small round snap "
  "button at its inner end near the collar. The shoulders look slightly more structured/defined (crisp shoulder seam), not padded. ")
KEEP = ("Keep EVERYTHING else EXACTLY identical to the input image: the same face, the same eyes and their size and shape, the same hair, "
  "the same line weight, flat cel shading, colours, pose, composition, background and lighting; the jacket stays white, cropped, "
  "with the same orange horizontal bands, the pale-blue dot patch on her left chest, the round '1420 MHz' patch ONLY on her LEFT "
  "sleeve, the same sleeves and cuffs; same black crop top and black trousers. No chest pocket, no extra patches, no text added. ")
SHEET_P = ("Edit this anime character turnaround sheet (front, three-quarter, side and back views). Apply the SAME change identically "
  "in all four views. " + JACKET + "In the side and back views the band collar wraps around the back of the neck and the epaulette "
  "is visible on top of the shoulder. " + KEEP + "Keep the back print (pale-blue circle and 'RARE EARTH') and the view labels "
  "exactly as they are.")
SHOT_P = ("Edit this anime film frame minimally. " + JACKET + "Where the shoulders or neck are hidden by hair, seat or framing, show "
  "only the visible part. " + KEEP)

def uri(im, mx=1536):
    im = im.copy(); im.thumbnail((mx, mx)); b = io.BytesIO(); im.save(b, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

def one(name, src, prompt, size, k, quality):
    im = Image.open(src).convert("RGB")
    if size == "1536x1024" and im.size != (1536, 1024):     # pad 16:9 frame to 3:2 with edge rows (cropped off after)
        c = Image.new("RGB", (1536, 1024)); c.paste(im.resize((1536, 864)), (0, 80))
        c.paste(im.resize((1536, 864)).crop((0, 0, 1536, 1)).resize((1536, 80)), (0, 0))
        c.paste(im.resize((1536, 864)).crop((0, 863, 1536, 864)).resize((1536, 80)), (0, 944)); im = c
    pl = {"prompt": prompt, "images": [uri(im, 1024)], "size": size, "quality": quality, "output_format": "jpeg"}
    out = f"{OUT}/cands/{name}_{k}"; err = None
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
            err = str(e)[:160]; print(name, k, "retry", att, err[:80], flush=True)
    rec = {"file": out + ".jpg", "job": name, "model": "openai/gpt-image-2", "quality": quality, "src": os.path.basename(src),
           "prompt": prompt, "secs": round(time.time() - t0, 1), "attempts": att + 1, "est_cost_usd": 0.07 * (att + 1), "error": err}
    with LOCK:
        L = json.load(open(PJ)) if os.path.exists(PJ) else []
        L.append(rec); json.dump(L, open(PJ, "w"), indent=1, ensure_ascii=False)
    print(name, k, rec["secs"], "ERR" if err else "ok", flush=True)

if __name__ == "__main__":
    os.makedirs(OUT + "/cands", exist_ok=True); a = sys.argv[1:]
    if a[0] == "sheet":
        tasks = [("sheet", os.environ.get("SHEET_SRC", A + "/CANON_SHEET.jpg"), os.environ.get("EXTRA", "") + SHEET_P, "1536x1024")]; a = a[1:]
    else:
        tasks = [(s, A + f"/shots/{s}.jpg", os.environ.get("EXTRA", "") + SHOT_P, "1536x1024") for s in a[1].split(",")]; a = a[2:]
    n = int(a[0]) if a else 1; k0 = int(a[1]) if len(a) > 1 else 0; q = a[2] if len(a) > 2 else "medium"
    with ThreadPoolExecutor(4) as ex:
        for t in tasks:
            for k in range(n): ex.submit(one, *t, k0 + k, q)
