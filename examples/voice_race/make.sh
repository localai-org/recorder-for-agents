#!/usr/bin/env bash
# Render the voice-detect.cpp two-engine VERIFY RACE (mp4 + gif, 16:9 + 1:1 square).
#
# Like image_race / face_carousel (and unlike record.sh/duel which capture a live
# terminal), this composes every frame itself with Pillow and stitches them with
# ffmpeg, so the content can be real audio: the SAME two real clips
# (clip_a.wav vs clip_b_same.wav) verified by TWO engines side by side
# (voice-detect.cpp ggml CLI vs onnxruntime), each progress bar filling at the
# REAL measured proc-time from spec.json. It makes NO speed claim: end to end the
# two engines are on par, so it leads from bit-exact parity + zero-Python instead.
#
#   ./make.sh                                      # uses VOICE_REPO (default ~/_git/voice-detect.cpp)
#   VOICE_REPO=/path/to/voice-detect.cpp ./make.sh
#   ./make.sh --dilate 0                           # extra renderer flags pass through
#
# env:
#   VOICE_REPO  built voice-detect.cpp checkout (provides tests/fixtures/*.wav)
#   PYTHON      python with Pillow + numpy (default: ~/recon-demos/venv/bin/python, then python3)
#   FPS / GIF_FPS  frame rates (defaults 20 / 14)
#
# spec.json (the REAL measured timing + verdict) ships in this dir. Regenerate it
# from a built checkout with: python voice-detect.cpp/benchmarks/demo/measure_voice.py
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

VOICE_REPO=${VOICE_REPO:-"$HOME/_git/voice-detect.cpp"}
FPS=${FPS:-20}
GIF_FPS=${GIF_FPS:-14}

# pick a python that has Pillow + numpy
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$HOME/recon-demos/venv/bin/python" ]; then
  PY="$HOME/recon-demos/venv/bin/python"
else
  PY="python3"
fi

mkdir -p "$HERE/out"

VOICE_REPO="$VOICE_REPO" "$PY" "$HERE/voice_race.py" \
  --spec "$HERE/spec.json" \
  --logo "$HERE/localai_logo.png" \
  --out "$HERE/out" \
  --fps "$FPS" --gif-fps "$GIF_FPS" \
  "$@"

echo "-> $HERE/out/voice_race.mp4"
echo "-> $HERE/out/voice_race.gif"
echo "-> $HERE/out/voice_race_square.mp4"
echo "-> $HERE/out/voice_race_square.gif"
