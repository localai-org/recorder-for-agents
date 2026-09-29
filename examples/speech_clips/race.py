#!/usr/bin/env python3
"""CPU diarization race: parakeet.cpp vs NeMo, each filling the 12.3 min timeline
at its real measured speed (bench/results: medians, inference only)."""
import argparse, json, os, subprocess, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--layout", default="square")
ap.add_argument("--data", default=os.path.join(HERE, "data"), help="dir with the traces + segments")
ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
ap.add_argument("--compiled-s", type=float, default=7.57, help="NeMo with compiled attention (non-default), for the footnote")
ap.add_argument("--agreement", default="99.95%", help="frame agreement with NeMo, shown on the end card")
ap.add_argument("--out", required=True)
a = ap.parse_args()
FPS = 30
_pk = json.load(open(os.path.join(a.data, "pkcpp_cpu.json")))
_ne = json.load(open(os.path.join(a.data, "nemo_cpu.json")))
PK_S, NEMO_S, NEMO_COMPILED_S = _pk["proc_s"], _ne["proc_s"], a.compiled_s
AUDIO_S = _pk["audio_s"]
LEAD, HOLD, CARD = 1.0, 1.4, 5.0
T_END = LEAD + NEMO_S + HOLD + CARD

BG = (13, 17, 23); INK = (230, 237, 243); DIM = (125, 133, 144); RULE = (48, 54, 61)
PANEL = (22, 27, 34)
SPK = [(240, 180, 41), (62, 200, 224), (224, 96, 126)]
HERO = (62, 200, 224); RIVAL = (150, 160, 175); GOLD = (240, 180, 41)


def font(name, size, weight):
    f = ImageFont.truetype(os.path.join(a.fonts, f"{name}.ttf"), size)
    f.set_variation_by_name(weight)
    return f


if a.layout == "square":
    W, H, S = 1080, 1080, 1.0
    ROW_Y = [230, 560]
else:
    W, H, S = 1080, 1920, 1.3
    ROW_Y = [560, 1040]
F_TITLE = font("SpaceGrotesk", int(48 * S), b"Bold")
F_SUB = font("JetBrainsMono", int(20 * S), b"Regular")
F_NAME = font("SpaceGrotesk", int(36 * S), b"Bold")
F_META = font("JetBrainsMono", int(18 * S), b"Regular")
F_BIG = font("SpaceGrotesk", int(44 * S), b"Bold")
F_LANE = font("JetBrainsMono", int(16 * S), b"Medium")
F_HUGE = font("SpaceGrotesk", int(120 * S), b"Bold")
F_CARD = font("SpaceGrotesk", int(30 * S), b"Medium")
F_SMALL = font("JetBrainsMono", int(17 * S), b"Regular")


def segs(path):
    return json.load(open(path))["segments"]


pk = segs(os.path.join(a.data, "pkcpp_cpu_f16_12min.json"))
nemo = segs(os.path.join(a.data, "nemo_cpu_fp32_12min.json"))


def frames(ss):
    out = {}
    for s in ss:
        out.setdefault(s["speaker"], set()).update(range(int(s["start"] * 10), int(s["end"] * 10)))
    return out


# map NeMo speaker ids onto parakeet.cpp's by best overlap, so colors match
fp, fn = frames(pk), frames(nemo)
best = max(itertools.permutations(fp.keys(), len(fn)) if len(fp) >= len(fn) else [tuple(fn.keys())],
           key=lambda p: sum(len(fn[n] & fp.get(q, set())) for n, q in zip(fn.keys(), p)))
remap = dict(zip(fn.keys(), best))
nemo = [dict(s, speaker=remap[s["speaker"]]) for s in nemo]
order = sorted({s["speaker"] for s in pk})


def mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def draw_row(dr, y, name, meta, color, ss, proc_s, t):
    m = 48
    run = max(0.0, t - LEAD)
    frac = min(1.0, run / proc_s)
    done = run >= proc_s
    dr.rounded_rectangle((m - 20, y - 24, W - m + 20, y + int(270 * S)), radius=18, fill=PANEL)
    dr.text((m, y), name, font=F_NAME, fill=color)
    dr.text((m, y + int(46 * S)), meta, font=F_META, fill=DIM)
    # timer (right)
    shown = min(run, proc_s)
    ttxt = f"{shown:5.2f} s"
    tw = dr.textlength(ttxt, font=F_BIG)
    dr.text((W - m - tw, y - 4), ttxt, font=F_BIG, fill=INK if not done else color)
    if done:
        star = "done"
        sw = dr.textlength(star, font=F_META)
        dr.text((W - m - sw, y + int(50 * S)), star, font=F_META, fill=color)
    # lanes
    lx0, lx1 = m + int(130 * S), W - m
    ly = y + int(96 * S)
    lh = int(24 * S)
    cut = frac * AUDIO_S
    for i, spk in enumerate(order):
        yy = ly + i * (lh + int(10 * S))
        dr.text((m, yy), f"SPEAKER {i + 1}", font=F_LANE, fill=SPK[i % 3])
        dr.line((lx0, yy + lh // 2, lx1, yy + lh // 2), fill=RULE, width=2)
        for s in ss:
            if s["speaker"] != spk or s["start"] >= cut:
                continue
            x0 = lx0 + s["start"] / AUDIO_S * (lx1 - lx0)
            x1 = lx0 + min(s["end"], cut) / AUDIO_S * (lx1 - lx0)
            dr.rectangle((x0, yy + 3, max(x1, x0 + 1), yy + lh - 3), fill=SPK[i % 3])
    # progress + rate
    py = ly + len(order) * (lh + int(10 * S)) + int(8 * S)
    px = lx0 + frac * (lx1 - lx0)
    dr.line((lx0, py, lx1, py), fill=RULE, width=4)
    dr.line((lx0, py, px, py), fill=color, width=4)
    rate = AUDIO_S / proc_s
    lbl = f"{mmss(cut)} / {mmss(AUDIO_S)} of audio   {rate:.0f}x real time"
    dr.text((lx0, py + int(10 * S)), lbl, font=F_META, fill=DIM)


def draw_card(dr, k):
    m = 60
    col = tuple(int(BG[i] + (c - BG[i]) * k) for i, c in enumerate(INK))
    y = int(H * 0.2)
    dr.text((m, y), f"{NEMO_S / PK_S:.1f}x faster", font=F_HUGE, fill=tuple(int(BG[i] + (c - BG[i]) * k) for i, c in enumerate(HERO)))
    y += int(150 * S)
    dr.text((m, y), "than NeMo, same CPU, same model", font=F_CARD, fill=col)
    y += int(90 * S)
    rows = [("parakeet.cpp", f"{PK_S:.1f} s", HERO),
            ("NeMo (default)", f"{NEMO_S:.1f} s", RIVAL),
            ("NeMo, compiled attention*", f"{NEMO_COMPILED_S:.1f} s", RIVAL)]
    for name, val, c in rows:
        cc = tuple(int(BG[i] + (x - BG[i]) * k) for i, x in enumerate(c))
        dr.text((m, y), name, font=F_CARD, fill=cc)
        vw = dr.textlength(val, font=F_CARD)
        dr.text((W - m - vw, y), val, font=F_CARD, fill=cc)
        y += int(52 * S)
    y += int(30 * S)
    notes = ["12.3 min, 3 speakers, Nemotron-3-Diarization, inference only",
             f"{a.agreement} of speech frames identical to NeMo",
             "* not NeMo's default on CPU",
             "GPU (GB10): 1.8 s vs 1.8 s, a tie at full precision"]
    for n in notes:
        dr.text((m, y), n, font=F_SMALL, fill=tuple(int(BG[i] + (x - BG[i]) * k) for i, x in enumerate(DIM)))
        y += int(30 * S)


def frame(t):
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    m = 48
    card_t = t - (LEAD + NEMO_S + HOLD)
    if card_t >= 0:
        draw_card(dr, 1.0)
        if card_t < 0.6:  # crossfade from the finished race into the results card
            return Image.blend(frame(LEAD + NEMO_S + HOLD - 1e-3), img, card_t / 0.6)
        return img
    hy = 50 if a.layout == "square" else 160
    if a.layout == "square":
        dr.text((m, hy), "Who spoke when, 12 minutes of audio", font=F_TITLE, fill=INK)
        sy = hy + int(66 * S)
    else:
        dr.text((m, hy), "Who spoke when,", font=F_TITLE, fill=INK)
        dr.text((m, hy + int(62 * S)), "12 minutes of audio", font=F_TITLE, fill=INK)
        sy = hy + int(130 * S)
    dr.text((m, sy), "speaker diarization, same CPU: Ryzen 9 9950X3D, 16 threads", font=F_SUB, fill=DIM)
    draw_row(dr, ROW_Y[0], "parakeet.cpp", "C++ / ggml, F16", HERO, pk, PK_S, t)
    draw_row(dr, ROW_Y[1], "NVIDIA NeMo", "PyTorch, FP32, default settings", RIVAL, nemo, NEMO_S, t)
    fy = H - int(70 * S)
    dr.text((m, fy), "real measured speed, not sped up · model load excluded", font=F_SMALL, fill=DIM)
    return img


enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
n = int(T_END * FPS)
for i in range(n):
    enc.stdin.write(frame(i / FPS).tobytes())
enc.stdin.close(); enc.wait()
print(a.out, n, "frames")
