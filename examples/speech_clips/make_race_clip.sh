#!/usr/bin/env bash
# Render the CPU diarization race (square + vertical) and crossfade into the end card.
# Uses the measured numbers in ./data (pkcpp_cpu.json, nemo_cpu.json + the two segment files).
# env: DATA (default ./data)  WORK (default ./work)  OUT (default ./out)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DATA=${DATA:-$HERE/data}; WORK=${WORK:-$PWD/work}; OUT=${OUT:-$PWD/out}; mkdir -p "$WORK" "$OUT"
for L in square vertical; do
  card="$WORK/card_$L.mp4"
  [ -f "$card" ] || python3 "$HERE/endcard.py" --layout $L --out "$card"
  python3 "$HERE/race.py" --layout $L --data "$DATA" --out "$WORK/race_$L.mp4"
  "$HERE/finish.sh" "$WORK/race_$L.mp4" "$card" "$OUT/race_cpu_$L.mp4" "${FADE:-0.7}"
done
