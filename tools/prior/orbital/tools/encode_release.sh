#!/usr/bin/env bash
# Encode the rendered frames (video/out/frames) + the final mix into the release files.
#
#   tools/encode_release.sh            # both files → release/
#
# A colored-pencil drawing redrawn 12 times a second is expensive to compress (fine hatching everywhere
# changes with every drawing), so the in-repo files are two-pass encodes sized to stay under GitHub's
# 100 MB per-file limit:
#   release/Orbital_Sunrise_1080p.mp4        HEVC (hvc1) 1080p24, AAC 192k  — best quality under the cap
#   release/Orbital_Sunrise_720p_h264.mp4    H.264 High 720p24, AAC 160k    — plays and uploads anywhere
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FR="$ROOT/video/out/frames/f%05d.jpg"
AUDIO="$ROOT/media/audio/Orbital_Sunrise_extended.wav"
[ -f "$AUDIO" ] || AUDIO="$ROOT/media/audio/Orbital_Sunrise_extended.m4a"
OUT="$ROOT/release"; mkdir -p "$OUT"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$AUDIO")
bits() { python3 -c "print(int(($1 * 8e6 / $DUR - $2 * 1e3) / 1e3))"; }   # target MB, audio kbps -> video kbps

# 1080p HEVC, ~94 MB
VB=$(bits 94 192)
echo "HEVC 1080p: ${VB}k video over ${DUR}s"
ffmpeg -y -loglevel error -stats -framerate 24 -i "$FR" -an -c:v libx265 -preset slow -b:v ${VB}k \
  -x265-params "pass=1:stats=$TMP/x265.log:aq-mode=3:log-level=error" -pix_fmt yuv420p -f null /dev/null
ffmpeg -y -loglevel error -stats -framerate 24 -i "$FR" -i "$AUDIO" -map 0:v -map 1:a \
  -c:v libx265 -preset slow -b:v ${VB}k -x265-params "pass=2:stats=$TMP/x265.log:aq-mode=3:log-level=error" \
  -tag:v hvc1 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -shortest "$OUT/Orbital_Sunrise_1080p.mp4"

# 720p H.264, ~90 MB
VB=$(bits 90 160)
echo "H.264 720p: ${VB}k video"
ffmpeg -y -loglevel error -stats -framerate 24 -i "$FR" -an -vf scale=1280:720:flags=lanczos -c:v libx264 -preset slow \
  -b:v ${VB}k -pass 1 -passlogfile "$TMP/x264" -pix_fmt yuv420p -f null /dev/null
ffmpeg -y -loglevel error -stats -framerate 24 -i "$FR" -i "$AUDIO" -map 0:v -map 1:a -vf scale=1280:720:flags=lanczos \
  -c:v libx264 -preset slow -profile:v high -b:v ${VB}k -pass 2 -passlogfile "$TMP/x264" -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart -shortest "$OUT/Orbital_Sunrise_720p_h264.mp4"

ls -la "$OUT"
