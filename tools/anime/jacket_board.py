"""Jacket boards: full sheets side by side + collar/shoulder close-ups (front, 3/4, side, back) per version.
Usage: jacket_board.py OUT.jpg LABEL=SHEET.jpg [LABEL=SHEET.jpg ...]   (paths relative to assets/character/anime/)"""
import sys
from PIL import Image, ImageDraw, ImageFont
D = "/home/user/rewind-music-video/assets/character/anime/"
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
CROPS = [(110, 110, 400, 330), (460, 110, 750, 330), (820, 110, 1110, 330), (1150, 100, 1500, 350)]
V = [a.split("=", 1) for a in sys.argv[2:]]; n = len(V); FW = 3072 // n; FH = FW * 2 // 3
B = Image.new("RGB", (3072, 44 + FH + n * (44 + 400)), (16, 16, 18)); d = ImageDraw.Draw(B)
for i, (lab, p) in enumerate(V):
    im = Image.open(D + p).convert("RGB")
    d.text((i * FW + 12, 8), lab, fill=(235, 235, 235), font=F); B.paste(im.resize((FW, FH)), (i * FW, 44))
    y = 44 + FH + i * 444; d.text((12, y + 8), lab + " close-ups: front / three-quarter / side / back", fill=(235, 235, 235), font=F)
    for j, c in enumerate(CROPS):
        t = im.crop(c); t = t.resize((round(400 * t.width / t.height), 400)); B.paste(t, (j * 768, y + 44))
B.save(sys.argv[1], quality=90); print(B.size)
