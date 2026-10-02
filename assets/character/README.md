# Jade character sheet candidates (assets/character)
Deliverables awaiting user approval. All were made with openai/gpt-image-2 (medium), conditioned on the refs listed in prompts.json.
- REVIEW_BOARD.jpg: A-D current age, E-H de-aged ~27. Each candidate sits next to its closest reference crop.
- FACE_SHEET_{cur,y27}.jpg (views + expressions), TURNAROUND_{cur,y27}.jpg, DRIVER_PLATE_{cur,y27}.jpg
- cands/: every generated candidate. prompts.json: model, prompt, refs, seed, scores, verdict, and SFace identity similarity.
- selection.json: which candidate became each deliverable.
- lines_check_*.jpg: sparse-line redraw sanity check (lines_check.py).
- Tools: gen.py (one gen), runq.py (job queue), facetools.py (YuNet + SFace crops, similarity and comparison montages; model files are in scratch).
Identity metric: mean SFace cosine against the 4 reference frontals. Two of her real photos score 0.56-0.77 against each other. Frontal candidates score 0.65-0.76.
