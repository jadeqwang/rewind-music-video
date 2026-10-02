import sys, numpy as np, cv2
sys.path.insert(0, "/home/user/rewind-music-video/tools/anime"); import framemeasure as FM
from PIL import Image, ImageDraw
A = "/home/user/rewind-music-video/assets/character/anime/"
shots = sys.argv[1].split(","); variants = sys.argv[2].split(",")   # e.g. "shots/{s}.jpg,v2/fp/{s}_0.jpg"
out = sys.argv[3]; MAN = {"J8b": (180, 300, 760, 864), "J7w": (330, 230, 700, 600)}
W = 600; rows = []
for s in shots:
    v1 = Image.open(A + f"shots/{s}.jpg").convert("RGB")
    if s in MAN: c = MAN[s]
    else:
        x0, y0, x1, y1 = FM.find_face(np.array(v1)); w = x1 - x0; cx = (x0 + x1) / 2
        c = (int(max(0, cx - 1.8 * w)), int(max(0, y0 - 0.2 * w)), int(min(1536, cx + 1.8 * w)), int(min(864, y1 + 1.6 * w)))
    tiles = []
    for v in variants:
        im = Image.open(A + v.format(s=s)).convert("RGB").resize((1536, 864)).crop(c)
        tiles.append(im.resize((W, round(W * im.height / im.width))))
    h = max(t.height for t in tiles); r = Image.new("RGB", (W * len(tiles), h + 24), (20, 20, 20)); d = ImageDraw.Draw(r)
    for i, t in enumerate(tiles): r.paste(t, (i * W, 24)); d.text((i * W + 6, 4), f"{s} {variants[i].format(s=s)}", fill=(255, 255, 0))
    rows.append(r)
B = Image.new("RGB", (W * len(variants), sum(r.height for r in rows)), (0, 0, 0)); y = 0
for r in rows: B.paste(r, (0, y)); y += r.height
B.save(out, quality=88); print(B.size)
