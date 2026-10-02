#!/usr/bin/env python3
"""Character-sheet candidate generator. Usage: gen.py ID MODEL KIND 'prompt' ref1,ref2,... [aspect]
Appends a record to prompts.json (score filled later)."""
import sys, json, os, time, random, fcntl
sys.path.insert(0, "/home/user/rewind-music-video/tools")
from cf import run_model, save_media, to_data_uri
D = "/home/user/rewind-music-video/assets/character"
R = D + ("/refs_768/" if os.environ.get("SMALLREFS") else "/refs_small/")
cid, model, kind, prompt, refs = sys.argv[1:6]
aspect = sys.argv[6] if len(sys.argv) > 6 else "16:9"
refs = [r for r in refs.split(",") if r]
uris = [to_data_uri(R + r) for r in refs]
seed = random.randint(1, 2**31 - 1)
sizes = {"16:9": "1536x1024", "3:2": "1536x1024", "1:1": "1024x1024", "3:4": "1024x1536", "2:3": "1024x1536"}
if model.startswith("google/nano-banana"):
    p = {"prompt": prompt, "image_input": uris[:14], "aspect_ratio": aspect, "output_format": "jpg", "image_size": "1K"}
elif model.startswith("bytedance/seedream"):
    wh = {"16:9": "2048x1152", "1:1": "2048x2048", "3:2": "2048x1365", "3:4": "1728x2304", "2:3": "1664x2496"}[aspect]
    p = {"prompt": prompt, "image": uris, "size": wh, "watermark": False}
elif model.startswith("xai/"):
    p = {"prompt": prompt, "images": [{"url": u} for u in uris[:5]], "aspect_ratio": aspect, "response_format": "b64_json"}
    if model.endswith("2.0"): p.update(resolution="1k", quality="medium")
elif model.startswith("openai/"):
    p = {"prompt": prompt, "images": uris, "size": sizes[aspect], "quality": "medium", "output_format": "jpeg"}
elif "flux-2" in model:
    w, h = {"16:9": (1536, 864), "1:1": (1024, 1024), "3:2": (1536, 1024), "3:4": (960, 1280), "2:3": (1024, 1536)}[aspect]
    p = {"prompt": prompt, "input_images": uris[:8], "width": w, "height": h, "seed": seed, "output_format": "jpeg", "safety_tolerance": 2}
elif "kontext" in model:
    p = {"prompt": prompt, "input_image": uris[0], "aspect_ratio": aspect, "seed": seed, "output_format": "jpeg"}
else:
    raise SystemExit("unknown model")
t0 = time.time()
rec = {"id": cid, "model": model, "kind": kind, "prompt": prompt, "refs": refs, "seed": seed, "aspect": aspect}
try:
    out = run_model(model, p, retries=0)
    paths = save_media(out, f"{D}/cands/{cid}")
    rec.update(file=os.path.relpath(paths[0], D), secs=round(time.time() - t0, 1))
    print(cid, "OK", paths, rec["secs"])
except Exception as e:
    rec.update(error=str(e)[:500], secs=round(time.time() - t0, 1))
    print(cid, "ERR", str(e)[:400])
with open(D + "/prompts.json.lock", "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    db = json.load(open(D + "/prompts.json")) if os.path.exists(D + "/prompts.json") else []
    db.append(rec)
    json.dump(db, open(D + "/prompts.json", "w"), indent=1)
