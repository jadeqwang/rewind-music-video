#!/usr/bin/env python3
"""Contact sheet: python3 tools/sets/sheet.py OUT.jpg img1 img2 ... [--lines]  (--lines adds XDoG line render row)"""
import sys, os, cv2, numpy as np
from PIL import Image, ImageDraw
def xdog(path, w=640):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE); h = int(im.shape[0] * w / im.shape[1])
    g = cv2.resize(im, (w * 2, h * 2), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    g = cv2.bilateralFilter(g, 9, 0.1, 5)
    s = 1.2; k = 1.6; p = 22; eps = 0.03; phi = 12
    a = cv2.GaussianBlur(g, (0, 0), s); b = cv2.GaussianBlur(g, (0, 0), s * k)
    d = (1 + p) * a - p * b
    e = np.where(d >= eps, 1.0, 1 + np.tanh(phi * (d - eps)))
    lines = (e < 0.5).astype(np.uint8) * 255   # white lines on black
    lines = cv2.resize(lines, (w, h), interpolation=cv2.INTER_AREA)
    return Image.fromarray(lines).convert("RGB")
args = [a for a in sys.argv[2:] if not a.startswith("--")]; lines = "--lines" in sys.argv
W = 640; tiles = []
for p in args:
    im = Image.open(p).convert("RGB"); im = im.resize((W, int(im.size[1] * W / im.size[0])))
    ImageDraw.Draw(im).text((6, 4), os.path.basename(os.path.dirname(p)) + "/" + os.path.basename(p), fill=(0, 255, 0))
    tiles.append(im)
H = 360; cols = min(len(tiles), 3); rows = -(-len(tiles) // cols) * (2 if lines else 1)
sheet = Image.new("RGB", (cols * W, rows * H), (40, 40, 40))
for i, t in enumerate(tiles):
    r, c = divmod(i, cols); r = r * (2 if lines else 1)
    sheet.paste(t.crop((0, 0, W, H)), (c * W, r * H))
    if lines: sheet.paste(xdog(args[i]).crop((0, 0, W, H)), (c * W, (r + 1) * H))
sheet.save(sys.argv[1], quality=88)
