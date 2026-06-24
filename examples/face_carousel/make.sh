#!/usr/bin/env bash
# Render the face-detect.cpp live RECOGNITION carousel (mp4 + gif).
#
# Unlike record.sh/duel/nemotron_race (which capture a live terminal), this
# composes every frame itself with Pillow and stitches them with ffmpeg, so the
# content can be real images: ~10 real faces, each with its REAL CLI outputs
# (detect score, 512-d embedding, age + gender) parsed live from the binary.
#
#   ./make.sh                                   # uses FACE_REPO (default ~/_git/face-detect.cpp)
#   FACE_REPO=/path/to/face-detect.cpp ./make.sh
#   ./make.sh --no-cache                        # re-run the CLI from scratch
#
# env:
#   FACE_REPO  built face-detect.cpp checkout (CLI + GGUF model + fixtures)
#   PYTHON     python with Pillow (default: ~/recon-demos/venv/bin/python, then python3)
#   FPS / GIF_FPS  frame rates (defaults 25 / 13)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

FACE_REPO=${FACE_REPO:-"$HOME/_git/face-detect.cpp"}
FPS=${FPS:-25}
GIF_FPS=${GIF_FPS:-13}

# pick a python that has Pillow
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$HOME/recon-demos/venv/bin/python" ]; then
  PY="$HOME/recon-demos/venv/bin/python"
else
  PY="python3"
fi

mkdir -p "$HERE/out"

FACE_REPO="$FACE_REPO" "$PY" "$HERE/face_carousel.py" \
  --logo "$HERE/localai_logo.png" \
  --out "$HERE/out" \
  --fps "$FPS" --gif-fps "$GIF_FPS" \
  "$@"

echo "-> $HERE/out/face_carousel.mp4"
echo "-> $HERE/out/face_carousel.gif"
