"""Extract plate frames for the renderer: media/plates/<id>/take<N>.mp4 → video/plates/<id>/f0001.jpg (24 fps, 960x540).

    python3 tools/extract_plates.py                  # latest take of every plate (skips up-to-date ones)
    python3 tools/extract_plates.py hero_sunrise:2   # a specific take
Writes video/plates/index.json with {id: {n, fps, w, h, take}}.
"""
import sys, json, pathlib, subprocess, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "media" / "plates", ROOT / "video" / "plates"
FPS, WD, HT = 24, 960, 540


def extract(pid, take=None):
    takes = sorted((SRC / pid).glob("take*.mp4"), key=lambda p: int(p.stem[4:]))
    if not takes:
        return None
    mp4 = SRC / pid / f"take{take}.mp4" if take else takes[-1]
    out = DST / pid
    stamp = out / ".take"
    if stamp.exists() and stamp.read_text() == mp4.name and any(out.glob("f*.jpg")):
        n = len(list(out.glob("f*.jpg")))
    else:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-vf",
                        f"fps={FPS},scale={WD}:{HT}:flags=lanczos", "-q:v", "3", str(out / "f%04d.jpg")], check=True)
        stamp.write_text(mp4.name)
        n = len(list(out.glob("f*.jpg")))
    mattes = len(list(out.glob("m*.png")))
    st = json.loads((out / "stats.json").read_text()) if (out / "stats.json").exists() else {}
    return {"n": n, "fps": FPS, "w": WD, "h": HT, "take": mp4.name, "mattes": mattes >= (n // 2), "gain": st.get("gain", 1.0)}


if __name__ == "__main__":
    DST.mkdir(parents=True, exist_ok=True)
    idx_path = DST / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    args = sys.argv[1:]
    todo = [a.split(":") for a in args] if args else [[p.name] for p in sorted(SRC.iterdir()) if p.is_dir()]
    for item in todo:
        pid, take = item[0], (item[1] if len(item) > 1 else None)
        info = extract(pid, take)
        if info:
            idx[pid] = info
            print(f"{pid}: {info}")
    idx_path.write_text(json.dumps(idx, indent=1))
