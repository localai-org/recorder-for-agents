# face_carousel: a live RECOGNITION reel for a .cpp engine (no recorder needed)

Most of this repo *captures* a live terminal into a video. Like
[`image_race`](../image_race), this recipe goes the other way: it **composes each
frame with Pillow** and stitches them with ffmpeg, so the content can be **real
images with real model output**.

It is not a speed race. It is a **capability reel**: drive the engine's real CLI
live over ~10 real inputs, and animate a per-item **recognition reveal** for each
one (a box draws in, landmarks pop, a result card fills with the genuine numbers),
carousel between them, and end on the LocalAI CTA card.

![face_carousel sample](out/face_carousel.gif)

The sample runs `face-detect.cpp`: the one binary does the whole InsightFace
pipeline (detect, 5-point align, 512-d recognition, age + gender) on 10 real
faces. Every number on screen (the 0.84 detect score, the scrolling 512-d
embedding, the age, the gender) is parsed live from the JSON the CLI printed.

## Run

```sh
# needs a built face-detect.cpp checkout (CLI + GGUF model + tests/fixtures)
FACE_REPO=~/_git/face-detect.cpp ./make.sh
./make.sh --no-cache          # re-run the CLI from scratch (ignore the cache)
```

`make.sh` picks a Python with Pillow (`~/recon-demos/venv/bin/python`, else
`python3`), runs the renderer, and writes `out/face_carousel.mp4` +
`out/face_carousel.gif`. No Docker, no Xvfb, no image model, just the real CLI,
Pillow, and ffmpeg. Knobs: `FACE_REPO`, `PYTHON`, `FPS`, `GIF_FPS`; the renderer
also takes `--cli/--model/--fixtures/--logo/--out` directly.

## The technique (reusable for ANY LocalAI .cpp engine)

This is the part to steal. The renderer is ~650 lines of Pillow; the shape is
generic and only two seams are engine-specific.

### 1. Drive the real CLI live to get genuine output

`gather()` shells out to the built binary and parses its `--json`:

```python
def run_json(cli, args):
    out = subprocess.run([cli, *args, "--json"], capture_output=True, text=True)
    return json.loads(out.stdout)        # detect / analyze / embed ...
```

For face it calls `detect` (boxes + 5 landmarks), `analyze` (age, gender, score),
and `embed` (the 512-d vector). The per-item dict it builds is **the only thing
the frame loop reads**, so retargeting the demo is just "fill that dict from a
different CLI".

### 2. Real inputs only, no synthetic

Inputs come from the engine's **in-repo real fixtures** (`tests/fixtures/`):
a group photo we detect ~11 faces in and crop the cleanest, plus three crisp
portraits. We crop the **real detections** (real box + landmarks, transformed
into the crop frame by `_square_crop`'s `map_pt`), never a hand-drawn stand-in.

### 3. The honest rule

No fabricated claims. Speed bars, scores, dims, ages: all are the real CLI
numbers. The only non-measured copy is the parity line
("bit-exact vs InsightFace"), which is itself a verified fact, not a vibe. If you
adapt this, keep that discipline: if a number isn't on the CLI's stdout, it
doesn't go on screen.

### 4. The per-item recognition reveal (the animation)

Each item plays a short phased timeline, all easing-driven (`ease_out`,
`ease_out_back`, `ease_in_out`):

| phase  | what animates |
|--------|---------------|
| `in`   | card + panel slide/fade in |
| `scan` | a teal sweep line crosses the thumbnail; the **box grows from its center**; the 5 landmarks **pop in sequence** (back-ease) |
| `reveal` | result card fills: a check stroke draws, the live embedding tick starts scrolling, the age/gender/score KV cards rise |
| `hold` | brief dwell; the embedding window keeps ticking |
| `out`  | slide/fade out to the next item (skipped on the last → end card) |

`build_frames()` just emits N frames per phase at the target fps and appends them;
`render_carousel_frame(subjects, idx, phase, p, ...)` paints one frame for
progress `p` in `[0,1]`. That `(phase, p)` split is the whole engine, nothing is
pre-rendered.

### 5. End on the LocalAI CTA card

`draw_end_card()` shows a strip of all recognized items, the **logo**
(`localai_logo.png`, configurable via `--logo`), a headline, the parity line, and
**four links** (localai.io, the LocalAI repo, the engine repo, the GGUF repo).
Same finish as the `duel`/`nemotron_race` outros, drawn instead of muxed.

### 6. Pillow loop + ffmpeg encode (mp4 + palettegen/paletteuse gif)

Frames are written as `frame_%04d.png` into a temp dir, then:

```sh
# crisp mp4
ffmpeg -framerate 25 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 out.mp4
# clean gif: build an optimal palette, then apply it (avoids 256-colour banding)
ffmpeg ... -vf "fps=13,scale=900:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png
ffmpeg ... -i frame_%04d.png -i palette.png \
  -lavfi "fps=13,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" out.gif
```

The two-pass `palettegen`/`paletteuse` is what keeps the gif from looking like a
2010 gif: a per-clip optimal palette plus light bayer dithering.

### Layout: cols vs square

The sample is **cols** (16:9, 1280x720): face card on the left, recognition panel
on the right, best for a README hero or landscape post. For a feed, render a
**square** (1080x1080) variant by stacking the panel under the card instead of
beside it (drop `rx` to a second row and widen the card); the same frame loop and
encode apply. `image_race` shows the cols/square/vertical switch wired through
`make.sh` if you want all three.

## Adapt it to another engine

Two swaps, nothing else:

1. **Swap the CLI in `gather()`.** Call your binary's `--json` subcommands and
   fill the per-item dict. For a depth engine: run `depth`, store the colorized
   depth map as the `thumb` and min/max/median as the card fields. For a detector:
   run `detect`, store the boxes. For an ASR/audio engine: the "thumb" becomes a
   waveform/spectrogram and the reveal fills transcript + timings.
2. **Swap the per-item card fields** in `draw_reco_panel()` (the RECOGNIZED row,
   the live tick, the three KV cards) and the end-card copy/links. Keep the
   phase timeline, the easing, the palette, and the ffmpeg encode as-is.

Palette is the shared house dark (`#0d1117` bg, teal accent) so it matches the
other LocalAI .cpp demos. No em-dashes in any rendered text.
