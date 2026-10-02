"""Contact sheets from rendered frames, for reviewing the whole film at a glance.

    python3 tools/review_sheets.py [--every 1.0] [--cols 8] [--w 240] [--per 48] [--from 0] [--to 242.2]

Reads video/out/frames/f%05d.jpg (24 fps) and video/out/shots.json (node render.mjs --list --out=out/shots.json),
writes video/out/review/sheet_<start>.jpg, each tile labelled with its time and shot.
"""
import sys, json, pathlib, argparse
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FR, OUT = ROOT / "video" / "out" / "frames", ROOT / "video" / "out" / "review"
FPS = 24

ap = argparse.ArgumentParser()
ap.add_argument("--every", type=float, default=1.0)
ap.add_argument("--cols", type=int, default=8)
ap.add_argument("--w", type=int, default=240)
ap.add_argument("--per", type=int, default=48)
ap.add_argument("--from", dest="t0", type=float, default=0.0)
ap.add_argument("--to", dest="t1", type=float, default=242.2)
a = ap.parse_args()

shots = []
sp = ROOT / "video" / "out" / "shots.json"
if sp.exists():
    shots = json.loads(sp.read_text())
def shot_at(t):
    for name, s0, s1 in reversed(shots):
        if s0 <= t < s1:
            return name
    return ""

try:
    font = ImageFont.truetype(str(ROOT / "video" / "fonts" / "JetBrainsMono_normal_400.ttf"), 13)
except Exception:
    font = ImageFont.load_default()

OUT.mkdir(parents=True, exist_ok=True)
times, t = [], a.t0 + a.every / 2
while t < a.t1:
    times.append(round(t, 3)); t += a.every
h = round(a.w * 9 / 16)
for k in range(0, len(times), a.per):
    chunk = times[k:k + a.per]
    rows = (len(chunk) + a.cols - 1) // a.cols
    S = Image.new("RGB", (a.cols * a.w, rows * (h + 18)), (34, 34, 34))
    d = ImageDraw.Draw(S)
    for i, t in enumerate(chunk):
        f = FR / f"f{int(round(t * FPS)):05d}.jpg"
        x, y = (i % a.cols) * a.w, (i // a.cols) * (h + 18)
        if f.exists():
            S.paste(Image.open(f).convert("RGB").resize((a.w, h), Image.LANCZOS), (x, y))
        d.text((x + 4, y + h + 2), f"{t:6.1f} {shot_at(t)}", fill=(220, 220, 220), font=font)
    out = OUT / f"sheet_{chunk[0]:06.1f}.jpg"
    S.save(out, quality=88)
    print(out)
