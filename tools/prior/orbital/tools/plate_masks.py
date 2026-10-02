"""Subject mattes for plates (rembg, isnet-general-use), at 12 fps: video/plates/<id>/m%04d.png (512x288, grey).

The matte lets the renderer tell a subject's shadow side (drawn in blue) from the void (left as black paper),
trace a clean silhouette contour, and pass procedural light behind the subject.
Frame f uses matte m(f rounded to odd), i.e. masks exist for f = 1, 3, 5, ...

    python3 tools/plate_masks.py [ids...]
"""
import sys, os, pathlib, time
os.environ.setdefault("U2NET_HOME", "/tmp/work/u2")
from PIL import Image
from rembg import remove, new_session

ROOT = pathlib.Path(__file__).resolve().parent.parent
DST = ROOT / "video" / "plates"
SES = new_session("isnet-general-use")


def run(pid):
    d = DST / pid
    frames = sorted(d.glob("f*.jpg"))
    todo = [f for f in frames if int(f.stem[1:]) % 2 == 1 and not (d / f"m{f.stem[1:]}.png").exists()]
    t0 = time.time()
    for f in todo:
        im = Image.open(f).convert("RGB").resize((512, 288))
        m = remove(im, session=SES, only_mask=True)
        m.save(d / f"m{f.stem[1:]}.png", optimize=True)
    if todo:
        print(f"{pid}: {len(todo)} mattes in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ids = sys.argv[1:] or [p.name for p in sorted(DST.iterdir()) if p.is_dir()]
    for pid in ids:
        run(pid)
