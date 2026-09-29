#!/usr/bin/env bash
# Render one film excerpt (square + vertical) and crossfade each into the end card.
#
#   make_film_clip.sh <name> <video> <t0> <t1> "<footer stat>" "<film credit>"
#
# needs <DATA>/<name>.sas.json and <DATA>/<name>.sounds.json (see README, "Data").
# env: DATA (default ./work)  OUT (default ./out)  FADE (crossfade seconds, default 0.7)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
n=$1; vid=$2; t0=$3; t1=$4; stat=$5; credit=$6
DATA=${DATA:-$PWD/work}; OUT=${OUT:-$PWD/out}; mkdir -p "$OUT" "$DATA"
for L in square vertical; do
  card="$DATA/card_$L.mp4"
  [ -f "$card" ] || python3 "$HERE/endcard.py" --layout $L --out "$card"
  python3 "$HERE/render_film.py" --layout $L --video "$vid" \
    --sas "$DATA/$n.sas.json" --sounds "$DATA/$n.sounds.json" \
    --t0 "$t0" --t1 "$t1" --stat "$stat" --credit "$credit" --out "$DATA/${n}_$L.mp4"
  "$HERE/finish.sh" "$DATA/${n}_$L.mp4" "$card" "$OUT/${n}_$L.mp4" "${FADE:-0.7}"
done
