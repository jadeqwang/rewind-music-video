from PIL import Image, ImageDraw, ImageFont, ImageOps
D = "/home/user/rewind-music-video/assets/character/anime/"
try: F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
except Exception: F = ImageFont.load_default()
def tile(p, w, h):
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB"); im = ImageOps.contain(im, (w, h))
    c = Image.new("RGB", (w, h), (24, 24, 28)); c.paste(im, ((w - im.width) // 2, (h - im.height) // 2)); return c
rows = [
 [("refs/jade/Pasted image.png (approved original)", "../../../refs/jade/Pasted image.png"), ("CANON_SHEET: black pants, no antenna, no headphones, original faces pasted back", "CANON_SHEET.jpg")],
 [("Expressions (E_expr2_0)", "cands/E_expr2_0.jpg"), ("Keyframe: centre-lock performance, siren rim (K_perform_0)", "cands/K_perform_0.jpg")],
 [("Keyframe: night drive LHD, sirens in mirror (K_drive_1)", "cands/K_drive_1.jpg"), ("Keyframe alt (K_drive_0)", "cands/K_drive_0.jpg")],
]
app = [("APPENDIX: alt canon edit S_canon_0", "cands/S_canon_0_fp.jpg"), ("APPENDIX: alt expr (half-body) E_expr_0", "cands/E_expr_0.jpg"),
       ("APPENDIX: from-photo design C_geomlock (superseded)", "cands/C_geomlock_0.jpg"), ("real photo PXL_20260528", "../../../refs/jade/PXL_20260528_215628802.jpg")]
W, TW, TH, LH = 3072, 1536, 1024, 44
AW, AH = 768, 512
B = Image.new("RGB", (W, len(rows) * (TH + LH) + AH + LH), (16, 16, 18)); d = ImageDraw.Draw(B); y = 0
for r in rows:
    for i, (lab, p) in enumerate(r):
        d.text((i * TW + 12, y + 8), lab, fill=(235, 235, 235), font=F); B.paste(tile(D + p, TW, TH), (i * TW, y + LH))
    y += TH + LH
for i, (lab, p) in enumerate(app):
    d.text((i * AW + 8, y + 8), lab[:52], fill=(200, 200, 200), font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18) if hasattr(F, "path") else F)
    B.paste(tile(D + p, AW, AH), (i * AW, y + LH))
B.save(D + "ANIME_BOARD.jpg", quality=90); print(B.size)
