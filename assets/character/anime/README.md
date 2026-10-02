# Anime Jade (canonical = refs/jade/Pasted image.png)
User decisions: keep 1420 MHz + pale-blue-dot patches + back print; remove Yagi antenna and headphones; NO glasses; black pants.
- CANON_SHEET.jpg: gpt-image-2 edit of the original sheet (cands/S_canon_1), then the ORIGINAL faces pasted back pixel-exact
  (tools/anime/facepaste.py: template-match alignment, corr 0.96-0.99, offset <=1 px) because the edit shrank eye opening 9-15%.
- CANON_HEAD_front.jpg / CANON_HEAD_34.jpg: upscaled head crops (use as identity refs for any later gen).
- Picks: cands/E_expr2_0 (expressions), cands/K_perform_0, cands/K_drive_1 (alt K_drive_0). Board: ANIME_BOARD.jpg.
- Tools: tools/anime/edit.py (jobs+prompts), board.py, headmeasure.py, gen.py (superseded from-photo designs). Log: prompts.json.
- gpt-image-2 single-input edits at medium quality run 25-30 s (at the proxy limit); >=4 input images time out every time.
- SHOT FIRST FRAMES (2026-10-02): `shots/<SHOT>.jpg` (1536x864) + `_720.jpg` (Seedance input), board `shots/FIRST_FRAMES_ANIME.jpg`, raw cands +
  log in `shots/cands`, `shots/prompts.json`. Built by `tools/anime/shots.py`: car shots are edits of K_drive_1, J5 = K_perform_0, J5b an edit of it,
  scene shots (J7/J8) use ONE composite reference board image (sheet + head + set plate) as the input. Follow-up edits fixed patch side (1420 MHz
  patch only on the LEFT sleeve; the model kept putting it on the right) and the police car's position (J3). Eye gate / fix: `tools/anime/framemeasure.py`
  (`--fix` = size-only eye enlarge via likeness/warp.py; J6 and J9 were fixed). Clips: assets/clips/CLIPS.md (ANIME JADE section).
- JACKET v2 (2026-10-02, user): snap-tab ribbed BAND COLLAR + snap EPAULETTES (real costume: Wild Fable mini cropped racer jacket, white); all else unchanged.
  `CANON_SHEET_v2.jpg` = v2/cands/sheet_0 (gpt-image-2 edit of CANON_SHEET.jpg, faces pasted back from CANON_SHEET, corr 0.97-0.98, offset <=1 px).
  Board `JACKET_v2_BOARD.jpg`. First frames `shots/<SHOT>_v2(_720).jpg`, board `shots/FIRST_FRAMES_ANIME_v2.jpg`. Tools: tools/anime/jacket_v2.py
  (edits, log v2/prompts.json), shotpaste.py (16:9 crop + v1 face paste-back), jacket_board.py. Picks: J7m and J8 = cand 1, all others cand 0.
- JACKET v3 (user feedback on v2 board: "I usually wear it open"): collar halves parted, snap tab unfastened/hanging, black mock-neck visible.
  `CANON_SHEET_v3.jpg` = v2/cands/sheet3_5 (edit of CANON_SHEET_v2, faces pasted back). Board `JACKET_v3_BOARD.jpg` (v1/v2/v3). First frames
  `shots/<SHOT>_v3(_720).jpg` (edits of the v2 frames, `jacket_v2.py shot3`), board `shots/FIRST_FRAMES_ANIME_v3.jpg`. v3 is CURRENT; v2 (closed) superseded.
  v3 picks: cand 1 for J2 J3 J5 J5b J6 J9, cand 0 for the rest.
