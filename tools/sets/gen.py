#!/usr/bin/env python3
"""Set/environment reference-sheet generator. Usage:
   python3 tools/sets/gen.py jobs.json      # jobs: [{"set","name","model","prompt","seed"?}]
Writes assets/sets/<set>/<name>.jpg and appends to assets/sets/prompts.json (exact prompt+model+seed+params+cost)."""
import sys, os, json, time, random, threading, io
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from cf import run_model, save_media
from PIL import Image

COST = {"xai/grok-imagine-image": 0.02, "xai/grok-imagine-image-quality": 0.05, "xai/grok-imagine-image-2.0": 0.04,
        "bytedance/seedream-5-pro": 0.045, "bytedance/seedream-4.5": 0.04, "bytedance/seedream-5-lite": 0.035, "google/nano-banana-pro": 0.14,
        "google/nano-banana-2": 0.07, "black-forest-labs/flux-2-pro-preview": 0.045,
        "black-forest-labs/flux-2-max": 0.10, "openai/gpt-image-2": 0.06}
LOCK = threading.Lock()
PJ = os.path.join(ROOT, "assets/sets/prompts.json")

def payload(model, prompt, seed):
    if model.startswith("xai/"):
        p = {"prompt": prompt, "aspect_ratio": "16:9", "response_format": "b64_json"}
        if model != "xai/grok-imagine-image-2.0": p["resolution"] = "1k"
        return p
    if model.startswith("bytedance/"):
        return {"prompt": prompt, "size": "1536x864", "watermark": False}
    if model.startswith("google/"):
        return {"prompt": prompt, "aspect_ratio": "16:9", "image_size": "1K", "output_format": "jpg"}
    if model.startswith("black-forest-labs/"):
        return {"prompt": prompt, "width": 1536, "height": 864, "seed": seed, "output_format": "jpeg", "safety_tolerance": 2}
    if model.startswith("openai/"):
        return {"prompt": prompt, "size": "1536x1024", "quality": "medium", "output_format": "jpeg"}
    raise ValueError(model)

def one(job):
    seed = job.get("seed") or random.randint(1, 2**31 - 1)
    pl = payload(job["model"], job["prompt"], seed)
    d = os.path.join(ROOT, "assets/sets", job["set"]); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, job["name"])
    t0 = time.time()
    try:
        r = run_model(job["model"], pl, timeout=60, retries=1, verbose=False)
        paths = save_media(r, out + "_raw")
        src = [p for p in paths if not p.endswith(".json")][0]
        im = Image.open(src).convert("RGB")
        w, h = im.size
        if abs(w / h - 16 / 9) > 0.02:   # center-crop to 16:9 (gpt-image is 3:2)
            nh = round(w * 9 / 16); top = (h - nh) // 2
            im = im.crop((0, top, w, top + nh))
        im.save(out + ".jpg", quality=93); size = im.size
        if src != out + ".jpg": os.remove(src)
        for p in paths:
            if p.endswith(".json") and os.path.exists(p): os.remove(p)
        err = None
    except Exception as e:
        err = str(e)[:400]; size = None
    rec = {"file": f"assets/sets/{job['set']}/{job['name']}.jpg", "set": job["set"], "model": job["model"],
           "prompt": job["prompt"], "seed": seed if "seed" in pl else None,
           "seed_note": None if "seed" in pl else "model has no seed param; not reproducible",
           "params": {k: v for k, v in pl.items() if k != "prompt"}, "size": size,
           "est_cost_usd": COST.get(job["model"]), "secs": round(time.time() - t0, 1), "error": err,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with LOCK:
        db = json.load(open(PJ)) if os.path.exists(PJ) else []
        db = [x for x in db if x["file"] != rec["file"]] + [rec]
        json.dump(db, open(PJ, "w"), indent=1)
    print(("ERR " + err) if err else "ok ", rec["file"], job["model"], rec["secs"], "s", flush=True)
    return rec

if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1]))
    with ThreadPoolExecutor(6) as ex:
        recs = list(ex.map(one, jobs))
    db = json.load(open(PJ))
    print("this batch $%.2f | total est $%.2f" % (sum(r["est_cost_usd"] or 0 for r in recs if not r["error"]),
          sum(x["est_cost_usd"] or 0 for x in db if not x["error"])))
