#!/usr/bin/env bash
# final_1080.sh: the final 1080p30 pass (audio v5final, Jade = anime-direct; both are the defaults in src/).
#   bash render/final_1080.sh frames     # 1) render 6,966 frames → render/frames/final1080 (≈2.1 h at ~1.1 s/frame, 3 workers; ~4 GB)
#   bash render/final_1080.sh encode     # 2) master + X-upload + <100 MB variants (≈40–60 min total, libx264 slow)
#   bash render/final_1080.sh all
# Frames are resumable: re-running `frames` without FORCE=1 only renders missing frames.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
FR="$HERE/frames/final1080"; OUT="$HERE/out"; WAV="$ROOT/assets/sound/Rewind5_final.wav"
DUR=232.2; N=6966   # 232.2 s × 30 fps (the song's last frame; matches the drafts)
mkdir -p "$OUT"

frames() {
  cd "$HERE"
  node render.mjs --range 0 $DUR --workers 3 --w 1920 --h 1080 --q 0.97 --dir frames/final1080 ${FORCE:+--force}
  local n; n=$(ls "$FR" | grep -c '^f[0-9]\{5\}\.jpg$'); [ "$n" -ge $N ] || { echo "only $n/$N frames"; exit 1; }
}

v_in=(-framerate 30 -start_number 0 -i "$FR/f%05d.jpg" -i "$WAV" -map 0:v -map 1:a -frames:v $N -t $DUR)
v_common=(-pix_fmt yuv420p -c:a aac -b:a 320k -ar 48000 -movflags +faststart)

twopass() {   # $1 = out file, $2 = video bitrate, $3 = maxrate, $4 = bufsize
  local log="$OUT/.2pass_$(basename "$1" .mp4)"
  ffmpeg -y -loglevel error "${v_in[@]}" -c:v libx264 -preset slow -b:v "$2" -maxrate "$3" -bufsize "$4" -pass 1 -passlogfile "$log" -an -f mp4 /dev/null
  ffmpeg -y -loglevel error "${v_in[@]}" -c:v libx264 -preset slow -b:v "$2" -maxrate "$3" -bufsize "$4" -pass 2 -passlogfile "$log" "${v_common[@]}" "$1"
  rm -f "$log"*
}

encode() {
  # master: quality-targeted (measured on 1080p test clips: ~8 Mbps calm shots, ~30 Mbps grainy rewinds at CRF 17 → ≈350–450 MB)
  ffmpeg -y -loglevel error "${v_in[@]}" -c:v libx264 -preset slow -crf 17 -tune grain "${v_common[@]}" "$OUT/REWIND_final_1080p_master.mp4"
  # X upload: 2-pass ~9 Mbps (≈265 MB; X's limit is 512 MB / 2:20 for non-Premium, so this needs a Premium account for 3:52)
  twopass "$OUT/REWIND_final_1080p_x.mp4" 9M 12M 18M
  # < 100 MB: 2-pass 3.0 Mbps video + 320k audio ≈ 96 MB (grain-heavy rewinds will soften / block)
  twopass "$OUT/REWIND_final_1080p_100mb.mp4" 3000k 4500k 6000k
  for f in master x 100mb; do p="$OUT/REWIND_final_1080p_$f.mp4"; printf '%-40s %s MB  ' "$(basename "$p")" "$(( $(stat -c%s "$p") / 1048576 ))"
    ffprobe -v error -show_entries format=duration,bit_rate -of csv=p=0 "$p"; done
}

case "${1:-all}" in frames) frames ;; encode) encode ;; all) frames; encode ;; *) echo "usage: $0 frames|encode|all"; exit 2 ;; esac
