#!/usr/bin/env python3
"""Generate the edit composites for first frames: python3 run.py J1 J2 ...  (max 3 parallel)"""
import json, sys, subprocess, os
from concurrent.futures import ThreadPoolExecutor
ROOT = "/home/user/rewind-music-video"; D = ROOT + "/assets/character/firstframes"
S = json.load(open(D + "/shots.json")); C = S["_common"]
def one(sid, tag=""):
    s = S[sid]; refs = s["src"] + ("," + s["set"] if s.get("set") else "")
    env = dict(os.environ, GEN2_DIR=D)
    r = subprocess.run(["python3", ROOT + "/assets/character/v2/gen2.py", f"{sid}{tag}", s["prompt"] + " " + C, refs, "1536x1024", "medium"], env=env, capture_output=True, text=True)
    return r.stdout.strip()
ids = sys.argv[1:]; tag = os.environ.get("TAG", "")
with ThreadPoolExecutor(3) as ex:
    for o in ex.map(lambda i: one(i, tag), ids): print(o)
