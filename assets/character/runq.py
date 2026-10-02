#!/usr/bin/env python3
"""Run a JSON list of jobs [{id,model,kind,prompt,refs:[..],aspect,small}] with N parallel workers via gen.py."""
import json, sys, subprocess, os
from concurrent.futures import ThreadPoolExecutor
jobs = json.load(open(sys.argv[1])); n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
def go(j):
    env = dict(os.environ); 
    if j.get("small"): env["SMALLREFS"] = "1"
    r = subprocess.run(["python3", "/home/user/rewind-music-video/assets/character/gen.py", j["id"], j["model"], j["kind"],
                        j["prompt"], ",".join(j["refs"]), j.get("aspect", "16:9")], capture_output=True, text=True, env=env)
    print(r.stdout.strip() or r.stderr.strip()[-300:], flush=True)
with ThreadPoolExecutor(n) as ex: list(ex.map(go, jobs))
