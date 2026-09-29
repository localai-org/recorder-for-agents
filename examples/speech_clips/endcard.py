#!/usr/bin/env python3
"""Animated end card: what parakeet.cpp is + where to get it. Writes a silent MP4.

  endcard.py --layout square|vertical --secs 4.5 --out card.mp4
"""
import argparse, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--layout", default="square")
ap.add_argument("--secs", type=float, default=4.5)
ap.add_argument("--logo", default=os.path.join(HERE, "..", "voice_race", "localai_logo.png"))
ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
ap.add_argument("--png", default="", help="also save the final frame here")
ap.add_argument("--out", required=True)
a = ap.parse_args()
FPS = 30

BG = (13, 17, 23); INK = (230, 237, 243); DIM = (125, 133, 144); PANEL = (22, 27, 34)
TEAL = (62, 200, 224); AMBER = (240, 180, 41); ROSE = (224, 96, 126); GREEN = (156, 204, 101)

W, H, S = (1080, 1080, 1.0) if a.layout == "square" else (1080, 1920, 1.4)


def font(name, size, weight):
    f = ImageFont.truetype(os.path.join(a.fonts, f"{name}.ttf"), int(size * S))
    f.set_variation_by_name(weight)
    return f


F_NAME = font("SpaceGrotesk", 96, b"Bold")
F_TAG = font("SpaceGrotesk", 36, b"Medium")
_tag_px = 36
while F_TAG.getlength("Open-source speech AI in C++. No Python.") > W - 2 * int(72 * S):
    _tag_px -= 1
    F_TAG = font("SpaceGrotesk", _tag_px, b"Medium")
F_ITEM = font("SpaceGrotesk", 34, b"Bold")
F_ITEMS = font("JetBrainsMono", 19, b"Regular")
F_META = font("JetBrainsMono", 19, b"Regular")
F_LINK = font("JetBrainsMono", 30, b"Bold")
F_BY = font("JetBrainsMono", 19, b"Regular")

logo = Image.open(a.logo).convert("RGBA")
lh = int(92 * S)
logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)

ITEMS = [(AMBER, "Speech to text", "NVIDIA Parakeet, 25 languages"),
         (TEAL, "Who spoke when", "NVIDIA Nemotron-3-Diarization, live or offline"),
         (GREEN, "What else is happening", "Xiaomi CED via ced.cpp, 527 sound classes")]


def mix(c, k):
    return tuple(int(BG[i] + (c[i] - BG[i]) * k) for i in range(3))


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def frame(t):
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    m = int(72 * S)
    y = int((H - 860 * S) / 2)

    def step(i):  # staggered reveal: element i fades + rises in
        k = ease((t - 0.12 * i) / 0.45)
        return k, int((1 - k) * 18 * S)

    k, dy = step(0)
    dr.text((m, y + dy), "parakeet.cpp", font=F_NAME, fill=mix(INK, k))
    y += int(118 * S)
    k, dy = step(1)
    dr.text((m, y + dy), "Open-source speech AI in C++. No Python.", font=F_TAG, fill=mix(DIM, k))
    y += int(92 * S)
    for i, (col, head, sub) in enumerate(ITEMS):
        k, dy = step(2 + i)
        dr.rectangle((m, y + dy + int(10 * S), m + int(8 * S), y + dy + int(66 * S)), fill=mix(col, k))
        dr.text((m + int(30 * S), y + dy), head, font=F_ITEM, fill=mix(INK, k))
        dr.text((m + int(30 * S), y + dy + int(46 * S)), sub, font=F_ITEMS, fill=mix(DIM, k))
        y += int(98 * S)
    k, dy = step(5)
    dr.text((m, y + dy + int(4 * S)), "CPU · CUDA · Metal · Vulkan  |  C API  |  MIT", font=F_META, fill=mix(DIM, k))
    y += int(70 * S)
    # links panel
    k, dy = step(6)
    ph = int(150 * S)
    dr.rounded_rectangle((m - int(24 * S), y + dy, W - m + int(24 * S), y + dy + ph), radius=int(18 * S), fill=mix(PANEL, k))
    dr.text((m, y + dy + int(28 * S)), "github.com/mudler/parakeet.cpp", font=F_LINK, fill=mix(TEAL, k))
    dr.text((m, y + dy + int(84 * S)), "localai.io", font=F_LINK, fill=mix(AMBER, k))
    y += ph + int(44 * S)
    # by the LocalAI team
    k, dy = step(7)
    lg = logo.copy()
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
    img.paste(lg, (m, y + dy), lg)
    dr.text((m + lg.width + int(22 * S), y + dy + (lh - int(22 * S)) // 2), "from the LocalAI team", font=F_BY, fill=mix(DIM, k))
    return img


enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18",
                        "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
n = int(a.secs * FPS)
for i in range(n):
    enc.stdin.write(frame(i / FPS).tobytes())
enc.stdin.close(); enc.wait()
if a.png:
    frame(a.secs).save(a.png)
print(a.out, n, "frames")
