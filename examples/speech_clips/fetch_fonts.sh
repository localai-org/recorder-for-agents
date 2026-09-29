#!/usr/bin/env bash
# Download the two OFL fonts the clips use (Space Grotesk + JetBrains Mono) into ./fonts.
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p fonts
base=https://github.com/google/fonts/raw/main/ofl
curl -sfL -o fonts/SpaceGrotesk.ttf   "$base/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
curl -sfL -o fonts/JetBrainsMono.ttf  "$base/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"
ls -la fonts
