#!/usr/bin/env python3
"""Burn parakeet.cpp output (speaker-attributed words + sound events) onto a film clip.

  render_film.py --video film.mp4 --sas film.sas.json --sounds film.sounds.json \
      --t0 214 --t1 252 --credit "Film: ..." --layout square|vertical --out clip.mp4

--sas is {"utterances":[..],"words":[..]} (parakeet_capi_transcribe_and_diarize_json,
or built from `parakeet-cli scene --json` with scene2sas.py) and --sounds is
[{label,start,end,peak}]. Times are film time in seconds. The film is decoded
with ffmpeg, overlays are drawn per frame with Pillow, and the film's own audio
is muxed back in.
"""
import argparse, json, os, subprocess, math
HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--layout", default="square")
ap.add_argument("--video", required=True)
ap.add_argument("--sas", required=True)
ap.add_argument("--sounds", required=True)
ap.add_argument("--t0", type=float, required=True, help="start of the excerpt in the film, seconds")
ap.add_argument("--t1", type=float, required=True, help="end of the excerpt in the film, seconds")
ap.add_argument("--stat", default="", help="footer line 1, e.g. the measured processing time")
ap.add_argument("--credit", default="", help="footer line 2: film title, licence, studio")
ap.add_argument("--min-peak", type=float, default=0.0)
ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
ap.add_argument("--out", required=True)
a = ap.parse_args()
FPS = 30
_pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                      "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout.split(",")
SRC_W, SRC_H = int(_pr[0]), int(_pr[1])
DUR = a.t1 - a.t0

BG = (13, 17, 23); INK = (230, 237, 243); DIM = (125, 133, 144); RULE = (48, 54, 61)
SPK = [(240, 180, 41), (62, 200, 224), (224, 96, 126), (180, 142, 173)]
SND = (156, 204, 101)


def font(name, size, weight):
    f = ImageFont.truetype(os.path.join(a.fonts, f"{name}.ttf"), size)
    f.set_variation_by_name(weight)
    return f


# ---------------------------------------------------------------- layout
if a.layout == "square":
    W, H = 1080, 1080
    # wide films keep their own height; taller ones (4:3) are cropped to 520 so captions stay clear of the picture
    VID = dict(w=1080, h=min(int(round(1080 * SRC_H / SRC_W / 2)) * 2, 520), y=150)
    S = 1.0
    CAP_Y, LANES_Y, FOOT_Y = 150 + VID["h"] + 28, 872, 1002
    CAP_LINES = 3 if VID["h"] <= 470 else 2
else:
    W, H = 1080, 1920
    VID = dict(w=1080, h=720, y=330)  # any aspect ratio is scaled to cover 1080x720 and cropped
    S = 1.3
    CAP_Y, LANES_Y, FOOT_Y = 1110, 1560, 1850
    CAP_LINES = 3

F_TITLE = font("SpaceGrotesk", int(46 * S), b"Bold")
F_SUB = font("JetBrainsMono", int(21 * S), b"Regular")
F_CAP = font("SpaceGrotesk", int(42 * S), b"Medium")
F_TAG = font("JetBrainsMono", int(20 * S), b"Bold")
F_CHIP = font("SpaceGrotesk", int(30 * S), b"Bold")
F_NOTE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(28 * S))
F_SMALL = font("JetBrainsMono", int(17 * S), b"Regular")
F_LANE = font("JetBrainsMono", int(17 * S), b"Medium")

# ---------------------------------------------------------------- data
d = json.load(open(a.sas))
order = []
for u in d["utterances"]:
    if u["speaker"] >= 0 and u["speaker"] not in order:
        order.append(u["speaker"])
num = {s: i for i, s in enumerate(order)}  # display index by first appearance
utts = []
for u in d["utterances"]:
    ws = [w for w in d["words"] if u["start"] - 0.01 <= w["start"] <= u["end"] + 0.01]
    utts.append(dict(spk=num.get(u["speaker"], -1), start=u["start"], end=u["end"], words=ws))
HIDE = set()
sounds = [dict(s, label=s["label"].split(",")[0]) for s in json.load(open(a.sounds))
          if s["start"] < a.t1 and s["end"] > a.t0 and s["label"] not in HIDE and s["peak"] >= a.min_peak]


# ---------------------------------------------------------------- drawing helpers
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def pill(dr, x, y, text, fnt, fg, bg, padx=14, pady=8):
    l, t, r, b = dr.textbbox((0, 0), text, font=fnt)
    w, h = r - l + 2 * padx, b - t + 2 * pady
    dr.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    dr.text((x + padx - l, y + pady - t), text, font=fnt, fill=fg)
    return w, h


def wrap(words, fnt, maxw, dr):
    lines, cur = [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if dr.textlength(nxt, font=fnt) > maxw and cur:
            lines.append(cur); cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def spk_label(i):
    return f"SPEAKER {i + 1}" if i >= 0 else "UNASSIGNED"


def spk_col(i):
    return SPK[i % len(SPK)] if i >= 0 else DIM


def draw_overlay(img, t):
    """t is film time (seconds)."""
    dr = ImageDraw.Draw(img, "RGBA")
    m = 48
    # header
    hy = 34 if a.layout == "square" else 120
    dr.text((m, hy), "parakeet.cpp", font=F_TITLE, fill=INK)
    tw = dr.textlength("parakeet.cpp", font=F_TITLE)
    dr.text((m + tw + 18, hy + int(22 * S)), "speech AI in C++", font=F_SUB, fill=SPK[1])
    dr.text((m, hy + int(62 * S)), "transcript + who is speaking + sound events, one pass", font=F_SUB, fill=DIM)

    # sound chip, top-right inside the video
    vy = VID["y"]
    active = [s for s in sounds if s["start"] <= t <= s["end"] + 0.6]
    cy = vy + 22
    for s in sorted(active, key=lambda s: -s["peak"])[:4]:
        k = ease((t - s["start"]) / 0.25)
        fade = 1.0 if t <= s["end"] else max(0.0, 1 - (t - s["end"]) / 0.6)
        txt = f"{s['label']}  {s['peak']:.2f}"
        l, tp, r, b = dr.textbbox((0, 0), txt, font=F_CHIP)
        nw = int(34 * S)
        cw = r - l + 36 + nw
        x = W - m - cw + int((1 - k) * 60)
        alpha = int(255 * k * fade)
        chip = Image.new("RGBA", (cw, b - tp + 22), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chip)
        cd.rounded_rectangle((0, 0, chip.width - 1, chip.height - 1), radius=chip.height // 2,
                             fill=SND + (alpha,))
        cd.text((18, 11 - tp + int(2 * S)), "♪", font=F_NOTE, fill=(16, 22, 12, alpha))
        cd.text((18 + nw - l, 11 - tp), txt, font=F_CHIP, fill=(16, 22, 12, alpha))
        img.paste(chip, (x, cy), chip)
        cy += chip.height + 12

    # captions
    cur = None
    for u in utts:
        if u["start"] <= t and (cur is None or u["start"] >= cur["start"]):
            cur = u
    if cur and t <= cur["end"] + 1.4:
        shown = [w["text"] for w in cur["words"] if w["start"] <= t]
        col = spk_col(cur["spk"])
        k = ease((t - cur["start"]) / 0.2)
        pill(dr, m, CAP_Y, spk_label(cur["spk"]), F_TAG, BG, col + (int(255 * k),))
        lines = wrap(shown, F_CAP, W - 2 * m, dr)
        y = CAP_Y + int(54 * S)
        for ln in lines[-CAP_LINES:]:
            dr.text((m, y), ln, font=F_CAP, fill=INK)
            y += int(54 * S)

    # speaker + sound lanes
    names = [(i, spk_label(i), spk_col(i)) for i in range(len(order))] + [(-2, "SOUNDS", SND)]
    lx0 = m + int(150 * S); lx1 = W - m
    y = LANES_Y
    gap = int(8 * S)
    lh = int(26 * S)
    # many speakers: shrink the lanes so they stay above the footer instead of running into it
    pitch = min(lh + gap, (FOOT_Y - 14 - LANES_Y) // len(names))
    if pitch < lh + gap:
        gap = max(2, pitch // 4)
        lh = pitch - gap
    for idx, name, col in names:
        dr.text((m, y - 2), name if idx != -2 else "SOUNDS", font=F_LANE, fill=col)
        dr.line((lx0, y + lh // 2 - 2, lx1, y + lh // 2 - 2), fill=RULE, width=2)
        spans = ([(u["start"], u["end"]) for u in utts if u["spk"] == idx] if idx != -2
                 else [(s["start"], s["end"]) for s in sounds])
        for s0, s1 in spans:
            s0, s1 = max(s0, a.t0), min(s1, t, a.t1)
            if s1 <= s0:
                continue
            x0 = lx0 + (s0 - a.t0) / DUR * (lx1 - lx0)
            x1 = lx0 + (s1 - a.t0) / DUR * (lx1 - lx0)
            dr.rounded_rectangle((x0, y + int(lh * 0.12), max(x1, x0 + 4), y + int(lh * 0.75)), radius=min(4, lh // 4), fill=col)
        y += lh + gap
    px = lx0 + (min(t, a.t1) - a.t0) / DUR * (lx1 - lx0)
    dr.line((px, LANES_Y - 6, px, y - 4), fill=INK, width=2)

    # footer
    dr.text((m, FOOT_Y), a.stat, font=F_SMALL, fill=DIM)
    dr.text((m, FOOT_Y + int(26 * S)), a.credit,
            font=F_SMALL, fill=DIM)


# ---------------------------------------------------------------- pipeline
# scale to cover the region, then crop; bias the crop a little above centre, where faces usually are
RW, RH = VID["w"], VID["h"]
_s = max(RW / SRC_W, RH / SRC_H)
_sw, _sh = int(math.ceil(SRC_W * _s / 2) * 2), int(math.ceil(SRC_H * _s / 2) * 2)
vf = f"scale={_sw}:{_sh},crop={RW}:{RH}:(in_w-out_w)/2:(in_h-out_h)*0.4,fps={FPS}"
vw, vh = RW, RH

dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", str(a.t0), "-t", str(DUR), "-i", a.video,
                        "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-ss", str(a.t0), "-t", str(DUR), "-i", a.video,
                        "-map", "0:v", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        "-af", f"afade=t=in:d=0.3,afade=t=out:st={DUR - 0.5}:d=0.5",
                        "-map_chapters", "-1", "-map_metadata", "-1", "-shortest", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
n = 0
fsz = vw * vh * 3
while True:
    buf = dec.stdout.read(fsz)
    if len(buf) < fsz:
        break
    t = a.t0 + n / FPS
    frame = Image.new("RGB", (W, H), BG)
    frame.paste(Image.frombytes("RGB", (vw, vh), buf), (0, VID["y"]))
    draw_overlay(frame, t)
    enc.stdin.write(frame.tobytes())
    n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print(f"{a.out}: {n} frames")
