#!/usr/bin/env python3
"""v2 generator: openai/gpt-image-2 with lean refs (long side <= REFMAX px), retries on the 30 s proxy cutoff.
Usage: gen2.py ID 'prompt' ref1,ref2 [size 1536x1024|1024x1536|1024x1024] [quality medium|low|high]
Refs are paths relative to the repo root. Appends a record to assets/character/v2/prompts_v2.json."""
import sys, os, json, time, io, fcntl, base64
sys.path.insert(0, "/home/user/rewind-music-video/tools")
from cf import run_model, save_media
from PIL import Image, ImageOps
ROOT = "/home/user/rewind-music-video"; D = os.environ.get("GEN2_DIR", ROOT + "/assets/character/v2")
REFMAX = int(os.environ.get("REFMAX", "768"))
cid, prompt, refs = sys.argv[1:4]
size = sys.argv[4] if len(sys.argv) > 4 else "1536x1024"
quality = sys.argv[5] if len(sys.argv) > 5 else "medium"
refs = [r for r in refs.split(",") if r]
uris = []
for r in refs:
    im = ImageOps.exif_transpose(Image.open(os.path.join(ROOT, r))).convert("RGB")
    im.thumbnail((REFMAX, REFMAX), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=88)
    uris.append("data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode())
p = {"prompt": prompt, "images": uris, "size": size, "quality": quality, "output_format": "jpeg"}
rec = {"id": cid, "model": "openai/gpt-image-2", "prompt": prompt, "refs": refs, "size": size, "quality": quality, "attempts": []}
for att in range(3):
    t0 = time.time()
    try:
        out = run_model("openai/gpt-image-2", p, retries=0, verbose=False)
        paths = save_media(out, f"{D}/cands/{cid}")
        rec.update(file=os.path.relpath(paths[0], D)); rec["attempts"].append(dict(ok=True, secs=round(time.time() - t0, 1)))
        print(cid, "OK", paths[0], round(time.time() - t0, 1)); break
    except Exception as e:
        rec["attempts"].append(dict(ok=False, secs=round(time.time() - t0, 1), err=str(e)[:200]))
        print(cid, "ERR", round(time.time() - t0, 1), str(e)[:200])
        if att == 1 and quality != "low":
            p["quality"] = "low"; rec["quality"] = "low"   # last resort: faster
with open(D + "/prompts_v2.lock", "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    db = json.load(open(D + "/prompts_v2.json")) if os.path.exists(D + "/prompts_v2.json") else []
    db.append(rec); json.dump(db, open(D + "/prompts_v2.json", "w"), indent=1)
