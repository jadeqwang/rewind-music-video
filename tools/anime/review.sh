#!/bin/bash
# Review one anime Jade take: probe, 6-frame contact sheet, eye-size gate on 8 frames.
# Usage: tools/anime/review.sh CLIP.mp4   -> analysis/clips_review/anime/<name>.jpg + .eyes.txt
R=/home/user/rewind-music-video; c=$1; n=$(basename "$c" .mp4); O=$R/analysis/clips_review/anime; mkdir -p $O
ffprobe -v error -select_streams v -show_entries stream=width,height,nb_frames,r_frame_rate -show_entries format=duration -of csv=p=0 "$c" | tr '\n' ' '; echo
python3 $R/tools/clip_review.py "$c" $O/$n.jpg >/dev/null 2>&1
python3 $R/tools/anime/framemeasure.py --clip "$c" 8 2>/dev/null | grep -v '^canon' > $O/$n.eyes.txt; tail -1 $O/$n.eyes.txt
