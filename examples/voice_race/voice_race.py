#!/usr/bin/env python3
r"""voice_race - the voice-detect.cpp VERIFY RACE: a two-engine speaker-verify
duel, voice-detect.cpp (ggml CLI) vs onnxruntime, both verifying the SAME pair of
real clips side by side, each pane revealing its two waveforms + a progress bar
that fills at the REAL measured proc-time, both landing on the identical verdict
(bit-exact embeddings), then a LocalAI end card.

This is NOT a speed-win demo. End to end the two engines are on par (ggml 30.0 ms
vs onnxruntime 33.5 ms, ~12 percent), so the demo deliberately makes NO speed
claim. It leads from the durable, honest wins instead: bit-exact parity with
onnxruntime and a zero-Python single static binary.

Pure Pillow frame synthesis + ffmpeg palettegen/paletteuse, same house treatment
as locate-anything.cpp/image_race and face-detect.cpp/face_carousel. The content
here is AUDIO: real waveforms of tests/fixtures/clip_a.wav vs clip_b_same.wav,
drawn in both panes. The timing + verdict numbers come from spec.json, which holds
REAL measured means (voicedetect-cli bench for ggml; onnxruntime CPU intra_op=8
for the reference). A verify computes two embeddings, so verify_ms = 2 * embed_ms.
--dilate only sets PLAYBACK speed, so a ~30 ms race is watchable in ~11 s without
faking anything.

This is the recorder-for-agents copy of the renderer that lives in
voice-detect.cpp/benchmarks/demo/voice_race.py. It is lightly de-hardcoded so every
path is configurable: point --fixtures / --spec / --logo (or the VOICE_REPO env
var) at a built voice-detect.cpp checkout and it renders the real clips.

  VOICE_REPO=~/_git/voice-detect.cpp python3 voice_race.py
  python3 voice_race.py --spec ./spec.json --out ./out

Renders out/voice_race.{mp4,gif} (16:9) + out/voice_race_square.{mp4,gif} (1:1).
The --cli / --model flags name the binary + GGUF that PRODUCED spec.json (see the
README on regenerating it); the render itself reads the measured numbers from
--spec. No em-dashes anywhere.
"""
import argparse, json, math, os, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
# The voice-detect.cpp checkout that holds the built CLI, GGUF model and fixtures.
# Override with VOICE_REPO=... or the explicit --cli/--model/--fixtures flags.
VOICE_REPO = Path(os.environ.get("VOICE_REPO", str(Path.home() / "_git" / "voice-detect.cpp")))
# logo painted on the end card; defaults to the copy that ships in this example dir.
LOGO_PATH = HERE / "localai_logo.png"

BG, PANEL, INK, DIM = (13, 17, 23), (22, 28, 36), (215, 221, 229), (110, 118, 129)
DIMMER = (96, 105, 117)
GRID = (34, 43, 52)
TEAL = (62, 200, 224)
SLATE = (150, 165, 180)
GREEN = (102, 214, 130)
GOLD = (240, 200, 90)
FPS = 20


def fontp(bold):
    return f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf"


def font(sz, bold=True):
    try:
        return ImageFont.truetype(fontp(bold), sz)
    except Exception:
        return ImageFont.load_default()


def load_wave_env(path, nbins):
    w = wave.open(str(path), "rb")
    n = w.getnframes()
    raw = w.readframes(n)
    w.close()
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    # per-bin peak envelope
    edges = np.linspace(0, len(a), nbins + 1).astype(int)
    env = np.array([np.max(np.abs(a[edges[i]:edges[i + 1]])) if edges[i + 1] > edges[i] else 0.0
                    for i in range(nbins)])
    m = env.max() or 1.0
    return env / m


def draw_wave(d, rect, env, color, reveal=1.0):
    """Center-line peak waveform inside rect, revealed left-to-right by `reveal`."""
    x, y, w, h = rect
    mid = y + h // 2
    n = len(env)
    bw = w / n
    cut = int(n * reveal)
    for i in range(n):
        bx = x + i * bw
        amp = env[i] * (h * 0.46)
        c = color if i < cut else GRID
        d.line([(bx, mid - amp), (bx, mid + amp)], fill=c, width=max(1, int(bw) - 1))
    d.line([(x, mid), (x + w, mid)], fill=(c if False else GRID), width=1)


def rounded(d, rect, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(rect, r, fill=fill, outline=outline, width=width)


def draw_brandline(cv, W, H, margin=40):
    """Persistent bottom CTA carried on every race frame (face-detect carousel
    treatment): project repo on the left, the LocalAI team tagline + localai.io
    on the right. Dim and tasteful, middle-dot separator, no em-dash."""
    d = ImageDraw.Draw(cv)
    fb = font(13, False)
    y = H - 30
    d.text((margin + 16, y), "github.com/mudler/voice-detect.cpp", font=fb, fill=DIMMER)
    t = "Brought to you by the LocalAI team  ·  localai.io"
    tw = d.textlength(t, font=fb)
    d.text((W - margin - 16 - tw, y), t, font=fb, fill=DIMMER)


def header(cv, W, spec):
    d = ImageDraw.Draw(cv)
    fh = font(26)
    ft = font(15, False)
    d.text((40, 24), "voice-detect.cpp", fill=TEAL, font=fh)
    x = 40 + d.textlength("voice-detect.cpp", font=fh)
    d.text((x + 14, 30), "vs", fill=DIM, font=ft)
    d.text((x + 40, 24), "onnxruntime", fill=INK, font=fh)
    note = f"WeSpeaker ResNet34 verify  -  {spec['threads']} CPU threads  -  bit-exact"
    d.text((W - 40 - d.textlength(note, font=ft), 30), note, fill=DIM, font=ft)
    d.line([40, 64, W - 40, 64], fill=GRID, width=1)
    # query pill: the verify being run
    fq = font(17)
    fpl = font(15, False)
    parts = [("verify", TEAL, fpl), ("  clip_a.wav  ", INK, fq), ("=?", DIM, fq),
             ("  clip_b_same.wav", INK, fq)]
    totw = sum(d.textlength(t, font=f) for t, _, f in parts) + 32
    px = 40
    rounded(d, [px, 76, px + totw, 110], 8, fill=PANEL, outline=GRID, width=1)
    tx = px + 16
    for t, c, f in parts:
        d.text((tx, 84), t, fill=c, font=f)
        tx += d.textlength(t, font=f)


def pane(cv, rect, spec, eng, frac, done_other, t_ms):
    d = ImageDraw.Draw(cv)
    ox, oy, pw, ph = rect
    accent = eng["accent"]
    done = frac >= 1.0
    rounded(d, [ox, oy, ox + pw, oy + ph], 12, fill=PANEL, outline=GRID, width=1)
    pad = 18
    ix = ox + pad
    iw = pw - 2 * pad
    # engine title
    fs = font(20)
    ft = font(14, False)
    d.text((ix, oy + 14), eng["label"], fill=accent, font=fs)
    d.text((ix, oy + 40), eng["device"], fill=DIM, font=ft)
    # two waveforms
    wy = oy + 66
    wh = 64
    for j, (lab, env) in enumerate(eng["_waves"]):
        ry = wy + j * (wh + 14)
        d.text((ix, ry - 1), lab, fill=DIM, font=font(13, False))
        wave_rect = (ix, ry + 16, iw, wh - 16)
        draw_wave(d, wave_rect, env, accent, reveal=min(1.0, frac * 1.15))
    # cosine bar label
    by = wy + 2 * (wh + 14) + 6
    d.text((ix, by), "speaker embedding match", fill=DIM, font=font(13, False))
    # progress bar
    pby = by + 22
    rounded(d, [ix, pby, ix + iw, pby + 9], 4, fill=(34, 41, 50))
    rounded(d, [ix, pby, ix + int(iw * min(1.0, frac)), pby + 9], 4, fill=accent)
    # status / verdict
    sy = pby + 22
    if done:
        verdict = spec["verdict"]
        fv = font(26)
        d.text((ix, sy), verdict, fill=GREEN, font=fv)
        sub = f"d={spec['distance']:.3f}   threshold {spec['threshold']:.2f}   verified"
        d.text((ix, sy + 32), sub, fill=INK, font=font(15, False))
        tline = f"verify in {eng['proc_ms']:.1f} ms   ({spec['threads']} threads)"
        d.text((ix, sy + 56), tline, fill=accent, font=font(16))
        # honest tag: both engines reach the IDENTICAL bit-exact verdict
        badge = "bit-exact match"
        bw = d.textlength(badge, font=font(14)) + 30
        bx = ix + iw - bw
        rounded(d, [bx, sy + 54, bx + bw, sy + 78], 6, outline=GREEN, width=2)
        d.ellipse([bx + 9, sy + 61, bx + 19, sy + 71], outline=GREEN, width=2)
        d.text((bx + 24, sy + 57), badge, fill=GREEN, font=font(14))
    else:
        d.text((ix, sy), "comparing embeddings", fill=accent, font=font(18))
        dots = "." * (1 + int((t_ms * 3) // 4) % 3)
        d.text((ix + d.textlength("comparing embeddings", font=font(18)) + 4, sy), dots,
               fill=accent, font=font(18))
        d.text((ix, sy + 30), f"{min(t_ms, eng['proc_ms']):.1f} ms", fill=INK, font=font(20))
    return done


def race_frame(W, H, spec, engines, w_elapsed, dilate):
    cv = Image.new("RGB", (W, H), BG)
    header(cv, W, spec)
    top = 150
    gap = 24
    pw = (W - 80 - gap) // 2
    ph = 376
    t_real = w_elapsed / dilate
    rects = [(40, top, pw, ph), (40 + pw + gap, top, pw, ph)]
    states = []
    for r, e in zip(rects, engines):
        frac = min(1.0, t_real / e["proc_s"])
        states.append(pane(cv, r, spec, e, frac, False, t_real * 1000.0))
    fy = top + ph + 30
    d = ImageDraw.Draw(cv)
    if all(states):
        foot = ("same WeSpeaker embedding, bit-exact (cosine parity 1.000)  -  "
                "on par end-to-end, zero Python")
        ff = font(16, False)
        d.text(((W - d.textlength(foot, font=ff)) // 2, fy), foot, fill=GREEN, font=ff)
    else:
        foot = "two engines, one bit-exact embedding  -  voice-detect.cpp ships as a single binary, no Python"
        ff = font(16, False)
        d.text(((W - d.textlength(foot, font=ff)) // 2, fy), foot, fill=DIM, font=ff)
    draw_brandline(cv, W, H)
    return cv


def race_frame_square(W, H, spec, engines, w_elapsed, dilate):
    """Square (1:1) re-lay of the verify race for social/mobile: the two engine
    panels stacked vertically (voice-detect.cpp on top, onnxruntime below), each
    with its waveforms + progress bar, the shared verify query in the header, the
    revealed verdict, and the persistent bottom CTA brandline."""
    cv = Image.new("RGB", (W, H), BG)
    header(cv, W, spec)
    top = 132
    gap = 22
    reserve = 122  # footer note + bottom brandline
    ph = (H - top - reserve - gap) // 2
    pw = W - 80
    t_real = w_elapsed / dilate
    rects = [(40, top, pw, ph), (40, top + ph + gap, pw, ph)]
    states = []
    for r, e in zip(rects, engines):
        frac = min(1.0, t_real / e["proc_s"])
        states.append(pane(cv, r, spec, e, frac, False, t_real * 1000.0))
    fy = top + 2 * ph + gap + 18
    d = ImageDraw.Draw(cv)
    if all(states):
        foot = ("same WeSpeaker embedding, bit-exact (cosine parity 1.000)  ·  "
                "on par end-to-end, zero Python")
        ff = font(15, False)
        d.text(((W - d.textlength(foot, font=ff)) // 2, fy), foot, fill=GREEN, font=ff)
    else:
        foot = "two engines, one bit-exact embedding  ·  single binary, no Python"
        ff = font(15, False)
        d.text(((W - d.textlength(foot, font=ff)) // 2, fy), foot, fill=DIM, font=ff)
    draw_brandline(cv, W, H)
    return cv


def end_card(W, H, spec):
    cv = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(cv)
    # subtle teal glow band
    logo = Image.open(LOGO_PATH).convert("RGBA")
    ls = 200
    logo = logo.resize((ls, ls), Image.LANCZOS)
    lx = (W - ls) // 2
    ly = int(H * 0.10)
    cv.paste(logo, (lx, ly), logo)
    fteam = font(18, False)
    team = "from the LocalAI team  ·  localai.io"
    d.text(((W - d.textlength(team, font=fteam)) // 2, ly + ls + 6), team, fill=DIM, font=fteam)
    # headline - the durable, honest win: bit-exact + dependency-free
    big = font(38)
    head = "Bit-exact with onnxruntime, zero Python"
    hw = d.textlength(head, font=big)
    if hw > W - 80:
        big = font(34)
        hw = d.textlength(head, font=big)
    hy = ly + ls + 46
    d.text(((W - hw) // 2, hy), head, fill=TEAL, font=big)
    sub = "same WeSpeaker embedding, one static binary, no torch, no onnxruntime"
    fsub = font(19, False)
    d.text(((W - d.textlength(sub, font=fsub)) // 2, hy + 52), sub, fill=INK, font=fsub)
    # honest detail line - on par end to end, no inflated ratio
    det = (f"end-to-end verify (2 embeds, {spec['threads']} threads, median): "
           f"ggml {spec['ggml_verify_ms']:.1f} ms  on par with  onnxruntime {spec['onnx_verify_ms']:.1f} ms")
    fdet = font(15, False)
    d.text(((W - d.textlength(det, font=fdet)) // 2, hy + 86), det, fill=DIM, font=fdet)
    # honest on-par bars: end-to-end verify ms (lower = faster), real measured
    bars = [("voice-detect.cpp", spec["ggml_verify_ms"], TEAL),
            ("onnxruntime", spec["onnx_verify_ms"], SLATE)]
    bx0 = int(W * 0.30)
    bw_full = int(W * 0.30)
    vmax = max(v for _, v, _ in bars)
    fb = font(17)
    by0 = hy + 138
    for i, (lab, v, c) in enumerate(bars):
        y = by0 + i * 40
        d.text((bx0 - d.textlength(lab, font=fb) - 16, y - 2), lab, fill=c, font=fb)
        rounded(d, [bx0, y, bx0 + bw_full, y + 16], 4, fill=(28, 35, 44))
        rounded(d, [bx0, y, bx0 + int(bw_full * v / vmax), y + 16], 4, fill=c)
        d.text((bx0 + bw_full + 16, y - 2), f"{v:.1f} ms", fill=INK, font=fb)
    # links - standing rule: localai.io + github.com/mudler/LocalAI (umbrella)
    # on the first row, the project repo + HF weights on the second.
    fl = font(17)
    gapx = 60

    def link_row(pair, y):
        widths = [d.textlength(t, font=fl) for t in pair]
        total = sum(widths) + gapx * (len(pair) - 1)
        x = (W - total) // 2
        for t, w in zip(pair, widths):
            d.text((x, y), t, fill=TEAL, font=fl)
            x += w + gapx

    row1 = ["localai.io", "github.com/mudler/LocalAI"]
    row2 = ["github.com/mudler/voice-detect.cpp",
            "huggingface.co/mudler/voice-detect-gguf"]
    link_row(row1, int(H * 0.83))
    link_row(row2, int(H * 0.89))
    return cv


def end_card_square(W, H, spec):
    """1:1 end card: same honest content as the 16:9 card (logo, team tagline +
    localai.io, the bit-exact headline, the on-par detail + bars, all four links),
    but laid out as one vertically-centred block so it reads at phone size. A green
    verdict line reinforces the SAME-SPEAKER result the race revealed."""
    cv = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(cv)
    cx = W // 2
    y = 168

    logo = Image.open(LOGO_PATH).convert("RGBA")
    ls = 188
    logo = logo.resize((ls, ls), Image.LANCZOS)
    cv.paste(logo, ((W - ls) // 2, y), logo)
    y += ls + 8

    fteam = font(18, False)
    team = "from the LocalAI team  ·  localai.io"
    d.text((cx - d.textlength(team, font=fteam) / 2, y), team, fill=DIM, font=fteam)
    y += 38

    big = font(36)
    head = "Bit-exact with onnxruntime, zero Python"
    hw = d.textlength(head, font=big)
    if hw > W - 80:
        big = font(32)
        hw = d.textlength(head, font=big)
    d.text((cx - hw / 2, y), head, fill=TEAL, font=big)
    y += 50

    sub = "same WeSpeaker embedding, one static binary, no torch, no onnxruntime"
    fsub = font(18, False)
    d.text((cx - d.textlength(sub, font=fsub) / 2, y), sub, fill=INK, font=fsub)
    y += 36

    det = (f"end-to-end verify (2 embeds, {spec['threads']} threads, median): "
           f"ggml {spec['ggml_verify_ms']:.1f} ms  on par with  "
           f"onnxruntime {spec['onnx_verify_ms']:.1f} ms")
    fdet = font(15, False)
    d.text((cx - d.textlength(det, font=fdet) / 2, y), det, fill=DIM, font=fdet)
    y += 42

    # honest on-par bars: end-to-end verify ms (lower = faster), real measured
    bars = [("voice-detect.cpp", spec["ggml_verify_ms"], TEAL),
            ("onnxruntime", spec["onnx_verify_ms"], SLATE)]
    bx0 = int(W * 0.34)
    bw_full = int(W * 0.30)
    vmax = max(v for _, v, _ in bars)
    fb = font(17)
    for i, (lab, v, c) in enumerate(bars):
        by = y + i * 40
        d.text((bx0 - d.textlength(lab, font=fb) - 16, by - 2), lab, fill=c, font=fb)
        rounded(d, [bx0, by, bx0 + bw_full, by + 16], 4, fill=(28, 35, 44))
        rounded(d, [bx0, by, bx0 + int(bw_full * v / vmax), by + 16], 4, fill=c)
        d.text((bx0 + bw_full + 16, by - 2), f"{v:.1f} ms", fill=INK, font=fb)
    y += 2 * 40 + 24

    # verdict reinforcement, straight from the race result (honest, real distance)
    fv = font(20)
    verdict = (f"{spec['verdict']}   d={spec['distance']:.3f} < {spec['threshold']:.2f}"
               f"   verified  ·  bit-exact match")
    d.text((cx - d.textlength(verdict, font=fv) / 2, y), verdict, fill=GREEN, font=fv)
    y += 56

    fl = font(17)
    gapx = 56

    def link_row(pair, ly):
        widths = [d.textlength(t, font=fl) for t in pair]
        total = sum(widths) + gapx * (len(pair) - 1)
        x = (W - total) // 2
        for t, w in zip(pair, widths):
            d.text((x, ly), t, fill=TEAL, font=fl)
            x += w + gapx

    link_row(["localai.io", "github.com/mudler/LocalAI"], y)
    link_row(["github.com/mudler/voice-detect.cpp",
              "huggingface.co/mudler/voice-detect-gguf"], y + 34)
    return cv


def main():
    global LOGO_PATH
    ap = argparse.ArgumentParser(description="two-engine speaker-verify race for voice-detect.cpp")
    ap.add_argument("--cli", default=str(VOICE_REPO / "build-cpu/examples/cli/voicedetect-cli"),
                    help="voicedetect-cli that PRODUCED spec.json (provenance; the render reads --spec)")
    ap.add_argument("--model", default=str(VOICE_REPO / "models/wespeaker_resnet34_f32.gguf"),
                    help="GGUF model that produced spec.json (provenance; the render reads --spec)")
    ap.add_argument("--fixtures", default=str(VOICE_REPO / "tests/fixtures"),
                    help="dir with clip_a.wav + clip_b_same.wav real clips")
    ap.add_argument("--spec", default=str(HERE / "spec.json"),
                    help="measured timing + verdict JSON (real numbers, not invented)")
    ap.add_argument("--logo", default=str(LOGO_PATH), help="LocalAI logo for the end card")
    ap.add_argument("--out", default=str(HERE / "out"),
                    help="output dir for voice_race.{mp4,gif} + the square cut")
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--gif-fps", type=int, default=14)
    ap.add_argument("--dilate", type=float, default=0.0, help="playback factor; 0 = auto ~11 s")
    ap.add_argument("--stills", action="store_true", help="also write still PNGs into the out dir")
    a = ap.parse_args()

    LOGO_PATH = Path(a.logo)
    spec = json.loads(Path(a.spec).read_text())
    fix = Path(a.fixtures)
    nbins = 150
    waves = [("clip_a.wav", load_wave_env(fix / "clip_a.wav", nbins)),
             ("clip_b_same.wav", load_wave_env(fix / "clip_b_same.wav", nbins))]
    engines = [
        {"label": "voice-detect.cpp", "device": "ggml CPU, 8 threads", "accent": TEAL,
         "proc_ms": spec["ggml_verify_ms"], "proc_s": spec["ggml_verify_ms"] / 1000.0,
         "winner": True, "_waves": waves},
        {"label": "onnxruntime", "device": "MLAS CPU, 8 threads", "accent": SLATE,
         "proc_ms": spec["onnx_verify_ms"], "proc_s": spec["onnx_verify_ms"] / 1000.0,
         "winner": False, "_waves": waves},
    ]
    proc_max = max(e["proc_s"] for e in engines)
    dilate = a.dilate if a.dilate > 0 else max(0.02, 11.0 / proc_max)
    wall = proc_max * dilate

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # 16:9 hero + 1:1 square variant for social/mobile.
    render(outdir / "voice_race.mp4", 1280, 720, spec, engines, dilate, wall,
           frame_fn=race_frame, card_fn=end_card,
           fps=a.fps, gif_fps=a.gif_fps, stills=a.stills, stills_dir=outdir)
    render(outdir / "voice_race_square.mp4", 1080, 1080, spec, engines, dilate, wall,
           frame_fn=race_frame_square, card_fn=end_card_square,
           fps=a.fps, gif_fps=a.gif_fps, stills=a.stills, stills_dir=outdir)


def render(out, W, H, spec, engines, dilate, wall, frame_fn, card_fn,
           fps, gif_fps, stills, stills_dir):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        k = 0
        for i in range(int(wall * fps) + 1):
            frame_fn(W, H, spec, engines, i / fps, dilate).save(tmp / f"f{k:05d}.png")
            k += 1
        hold = frame_fn(W, H, spec, engines, wall * 1.4, dilate)  # both fully done
        for _ in range(int(2.2 * fps)):
            hold.save(tmp / f"f{k:05d}.png")
            k += 1
        card = card_fn(W, H, spec)
        for _ in range(int(3.4 * fps)):
            card.save(tmp / f"f{k:05d}.png")
            k += 1
        if stills:
            stills_dir = Path(stills_dir)
            stills_dir.mkdir(parents=True, exist_ok=True)
            stem = out.stem
            hold.save(stills_dir / f"{stem}_still.png")
            card.save(stills_dir / f"{stem}_endcard.png")
            frame_fn(W, H, spec, engines, wall * 0.5, dilate).save(stills_dir / f"{stem}_midrace.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                        "-i", str(tmp / "f%05d.png"), "-pix_fmt", "yuv420p", str(out)], check=True)
        pal = tmp / "pal.png"
        gw = 900
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out),
                        "-vf", f"fps={gif_fps},scale={gw}:-1:flags=lanczos,palettegen=stats_mode=diff",
                        str(pal)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-i", str(pal),
                        "-lavfi", f"fps={gif_fps},scale={gw}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                        str(out.with_suffix(".gif"))], check=True)
    print("wrote", out, "+ gif")


if __name__ == "__main__":
    main()
