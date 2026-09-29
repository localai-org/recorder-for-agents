#!/usr/bin/env bash
# Join a rendered clip and the end card with a crossfade. The clip's audio fades
# out under the transition and the card is silent. Output length is fixed
# (clip + card - crossfade), so nothing can run away.
#   finish.sh content.mp4 card.mp4 out.mp4 [xfade_s]
set -euo pipefail
IN=$1; CARD=$2; OUT=$3; XF=${4:-0.7}
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
D=$(dur "$IN"); CD=$(dur "$CARD")
OFF=$(awk "BEGIN{print $D-$XF}"); AF=$(awk "BEGIN{print $D-1.0}"); TOT=$(awk "BEGIN{print $D+$CD-$XF}")
if [ -n "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$IN" | head -1)" ]; then
  AUD="[0:a]afade=t=out:st=${AF}:d=1.0,apad=whole_dur=${TOT}[au]"
else
  AUD="anullsrc=r=48000:cl=stereo,atrim=0:${TOT}[au]"
fi
ffmpeg -loglevel error -y -i "$IN" -i "$CARD" -filter_complex \
  "[0:v]fps=30,format=yuv420p,setsar=1[a];[1:v]fps=30,format=yuv420p,setsar=1[b];\
[a][b]xfade=transition=fade:duration=${XF}:offset=${OFF}[v];${AUD}" \
  -map "[v]" -map "[au]" -map_chapters -1 -map_metadata -1 -t "$TOT" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$OUT"
echo "-> $OUT ($(dur "$OUT")s)"
