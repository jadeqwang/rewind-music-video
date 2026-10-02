# Anime Jade (canonical = refs/jade/Pasted image.png)
User decisions: keep 1420 MHz + pale-blue-dot patches + back print; remove Yagi antenna and headphones; NO glasses; black pants.
- CANON_SHEET.jpg: gpt-image-2 edit of the original sheet (cands/S_canon_1), then the ORIGINAL faces pasted back pixel-exact
  (tools/anime/facepaste.py: template-match alignment, corr 0.96-0.99, offset <=1 px) because the edit shrank eye opening 9-15%.
- CANON_HEAD_front.jpg / CANON_HEAD_34.jpg: upscaled head crops (use as identity refs for any later gen).
- Picks: cands/E_expr2_0 (expressions), cands/K_perform_0, cands/K_drive_1 (alt K_drive_0). Board: ANIME_BOARD.jpg.
- Tools: tools/anime/edit.py (jobs+prompts), board.py, headmeasure.py, gen.py (superseded from-photo designs). Log: prompts.json.
- gpt-image-2 single-input edits at medium quality run 25-30 s (at the proxy limit); >=4 input images time out every time.
