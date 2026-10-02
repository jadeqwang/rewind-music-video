#!/usr/bin/env python3
"""Compact gate report: python3 tools/likeness/report.py IMG [IMG ...]  (multi-face aware)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS
SHOW = ["eye_w_face", "iris_face", "eye_open", "forehead", "upper_head", "forehead_w", "jaw_w", "chin_w"]
def rows(path, nt=None):
    out = []
    for j, e in enumerate(MS.measure_multi(path, nt)):
        m = e["m"]
        if not m: continue
        ok, dev, br = MS.gate(m)
        out.append(dict(file=os.path.basename(path), face=j, yaw=m["yaw"], ok=ok, dev=dev, brow={k: v["z"] for k, v in br.items()}, m=m))
    return out
if __name__ == "__main__":
    for p in sys.argv[1:]:
        nt = None
        if ":" in p: p, nt = p.split(":"); nt = int(nt)      # TURN.jpg:4 -> 4 figure tiles
        for r in rows(p, nt):
            print(f"{r['file'][:22]:22s} f{r['face']} yaw{r['yaw']:+5.0f} {'PASS' if r['ok'] else 'FAIL'} " +
                  " ".join(f"{k[:7]}{r['dev'].get(k, float('nan'))*100:+5.1f}" for k in SHOW) + "  browZ " + json.dumps(r["brow"]))
