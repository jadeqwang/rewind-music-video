"""Lip-sync report for candidate takes over the exact window each shot uses in the edit."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouth, score
P = "/tmp/work/sd/prod"
# shot -> (song t0 of clip, used window, fixed mouth ROI for extreme close-ups)
USED = {
 "sd02": (5.2, (5.70, 8.86), None), "sd03": (10.4, (10.88, 12.73), None), "sd05": (21.5, (23.17, 24.79), None),
 "sd06": (25.0, (25.30, 27.82), None), "sd07": (30.0, (30.98, 35.94), "roi"), "sd08": (35.5, (35.94, 39.95), None),
 "sd09": (61.4, (62.42, 63.23), None), "sd10": (71.0, (71.14, 75.36), None), "sd11": (75.0, (75.36, 77.66), None),
 "sd12": (81.0, (82.20, 84.60), None), "sd13": (93.3, (94.61, 97.45), None), "sd14": (97.2, (99.76, 100.75), None),
 "sd15": (102.8, (104.34, 107.79), "roi"), "sd16": (107.5, (107.79, 112.02), None),
}
ROI = {"sd07_transit__efef2556bd": (550, 420, 730, 530), "sd07_transit__ebebde7323": (550, 480, 730, 600),
       "sd15_own_ecu__7e97dfe5ee": (530, 410, 720, 540), "sd15_own_ecu__bac460481f": (540, 420, 740, 550)}
man = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seedance_manifest.json")))
# --hair v3: score only the takes of that character revision (default: the original v2 takes)
HAIR = sys.argv[sys.argv.index("--hair") + 1] if "--hair" in sys.argv else "v2"
REPORT = "/tmp/work/sync_report.json" if HAIR == "v2" else f"/tmp/work/sync_report_{HAIR}.json"
import mouth_color
out = json.load(open(REPORT)) if (os.path.exists(REPORT) and HAIR != "v2") else {}   # incremental for new revisions
for key, e in man.items():
    sid = key.split("_")[0]
    if sid not in USED:
        continue
    t0, win, mode = USED[sid]
    for t in e["takes"]:
        if t.get("state") != "done" or not t.get("file") or t.get("hair", "v2") != HAIR:
            continue
        name = os.path.basename(t["file"])[:-4]
        if name in out:
            continue
        roi = ROI.get(name) if mode == "roi" else None
        if mode == "roi" and roi is None:
            continue
        # secondary metric that survives profiles and push-ins (skin blob + mouth-interior colour)
        cv, _ = mouth_color.openness(t["file"])
        col = mouth_color.score(cv, t0, win)
        r = mouth.track(t["file"], fixed_roi=roi)
        if r["hit"] < 0.3:
            out[name] = {"shot": sid, "hit": round(r["hit"], 2), "color": col}
            print(f"{sid} {name}: face hit {r['hit']:.2f} (cascade skipped)  colour {col}", flush=True); continue
        s = score.score(r, "/tmp/work/vocals.wav", t0, max_lag=0.3, window=win)
        out[name] = {"shot": sid, "hit": round(r["hit"], 2), "lag": s["best_lag_s"], "corr": s["best_corr"], "corr0": s["corr_at_0"], "color": col}
        print(f"{sid} {name}: hit {r['hit']:.2f} lag {s['best_lag_s']:+.3f} corr {s['best_corr']:.2f} corr0 {s['corr_at_0']:.2f}  colour {col}", flush=True)
json.dump(out, open(REPORT, "w"), indent=1)
