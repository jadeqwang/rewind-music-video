"""JACKET_v2_BOARD.jpg: old vs new canon sheet + collar/shoulder close-ups (front, 3/4, side, back)."""
from PIL import Image, ImageDraw, ImageFont
D = "/home/user/rewind-music-video/assets/character/anime/"
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
CROPS = [(110, 120, 400, 330), (460, 120, 750, 330), (820, 120, 1110, 330), (1150, 100, 1500, 350)]
B = Image.new("RGB", (3072, 44 + 1024 + 2 * (44 + 400)), (16, 16, 18)); d = ImageDraw.Draw(B)
for i, (lab, p) in enumerate([("OLD: CANON_SHEET.jpg", "CANON_SHEET.jpg"), ("NEW: CANON_SHEET_v2.jpg (snap-tab band collar + snap epaulettes)", "CANON_SHEET_v2.jpg")]):
    im = Image.open(D + p).convert("RGB")
    d.text((i * 1536 + 12, 8), lab, fill=(235, 235, 235), font=F); B.paste(im, (i * 1536, 44))
    y = 44 + 1024 + i * 444; d.text((12, y + 8), lab.split(":")[0] + " close-ups: front / three-quarter / side / back", fill=(235, 235, 235), font=F)
    for j, c in enumerate(CROPS):
        t = im.crop(c); t = t.resize((round(400 * t.width / t.height), 400)); B.paste(t, (j * 768, y + 44))
B.save(D + "JACKET_v2_BOARD.jpg", quality=90); print(B.size)
