# REWIND — music video project brief (shared by all agents)

Repo root: /home/user/rewind-music-video  (branch claude/magical-faraday-dbldp4)
Audio: "Rewind (4).mp3" — 232.44 s, 48 kHz stereo, Suno, 124 BPM, E minor Phrygian. DO NOT modify the song.
Lyrics + Suno structure prompt: "Rewind lyrics and prompt.md"
Source poem "Reload" (and preceding poem "Initiative") in docs/inference_book.txt (poetry book "Inference" by Jade Q Wang).

## Story
Artist/vocalist Jade Wang. Nightmare the night before her dissertation defense (she had already started a NASA postdoc,
flew back to Chicago to defend). Speeding down Lake Shore Drive at night, a shadow chasing her. Silent sirens in rear view.
Loop 1: pulls over, 3-4 men in shades and suits approach, she shows ID, gets shot -> time stops -> Braid-like REWIND.
Loop 2: bolts, zigzags across a grassy field, they're too fast -> shot -> rewind.
Loop 3: doesn't stop, doesn't pull over, keeps driving inconspicuously. "Never stop."
Subtext (poem "Initiative" right before "Reload"): Chinese-American scientist paranoia — Qian Xuesen, Wen Ho Lee,
"always pack a go bag", "be careful what you post". The suits = federal agents. Threat assessment vs. trauma.
Theme: performance anxiety + paranoia overcome by brute-force logic — playing out every chess move / search tree
until you find the line where you don't die. The defense (proof) and the escape are the same search.

## Deliverable
A music video (16:9, 1920x1080, 30fps) using the exact audio. Final pixels are drawn by a deterministic JavaScript
canvas renderer (rendered headless with Playwright -> ffmpeg). Seedance video generations (characters + sets) are used
as ROTOSCOPE BASES: we extract motion/edges/masks/depth from them and redraw in our own style; the raw gen footage is
not shown directly (or only heavily processed). Kinetic lyric typography is a first-class element.

## Rules for agents
- Keep scratch/big intermediates in /home/user/rewind-music-video/{analysis,assets,render} ; note large binaries
  (>50MB) must not be committed. Write a short README/notes file for what you produced.
- Report back concise conclusions (paths, key numbers, what works / doesn't), not file dumps.
- Cloudflare API is reachable via proxy at api.cloudflare.com (auth injected automatically; no key needed).
- Chromium for Playwright at /opt/pw-browsers (do not run playwright install).
