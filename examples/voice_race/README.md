# voice_race: a two-engine VERIFY RACE for a .cpp engine (no recorder needed)

Most of this repo *captures* a live terminal into a video. Like
[`image_race`](../image_race) and [`face_carousel`](../face_carousel), this recipe
goes the other way: it **composes each frame with Pillow** and stitches them with
ffmpeg, so the content can be **real input with real, measured numbers**.

It is a **duel**: the SAME real input is run through **two engines** side by side
(the ggml `.cpp` engine vs its reference framework), each pane reveals that
engine's real output, and each engine's progress bar fills at its **real measured
proc-time**. The faster bar nudges ahead, both land on the **identical verdict**,
and it ends on the LocalAI CTA card.

![voice_race sample](out/voice_race.gif)

The sample runs `voice-detect.cpp` vs `onnxruntime` on a speaker-verify: the two
real clips `clip_a.wav` and `clip_b_same.wav` are drawn as waveforms in **both**
panes, both engines compute a WeSpeaker ResNet34 embedding, and both reveal the
same verdict (`SAME SPEAKER  d=0.197 < 0.25`). The timing bars fill at the real
measured means in `spec.json` (ggml **30.0 ms** vs onnxruntime **33.5 ms**
end-to-end verify).

## The honest rule comes first here

This demo deliberately makes **NO speed-win claim**. End to end the two engines
are **on par** (~12 percent), and by best-case `min` onnxruntime is actually
faster. Inventing a "1.5x faster" headline would be a lie, so the demo does not.
Instead it leads from the two **durable, honest** wins: **bit-exact parity** with
onnxruntime (identical embedding, cosine 1.000) and a **zero-Python single static
binary**. The race is the hook; the end card is the truth.

That is the reusable discipline: **if it is not a clean win, frame it as "on par"
and lead with bit-exact + zero-dependency.** Every number on screen is read from
`spec.json`, which is a real measurement, never a vibe.

## Run

```sh
# needs a voice-detect.cpp checkout for the real clips (tests/fixtures/*.wav)
VOICE_REPO=~/_git/voice-detect.cpp ./make.sh
./make.sh --dilate 0          # extra renderer flags pass through
```

`make.sh` picks a Python with Pillow + numpy (`~/recon-demos/venv/bin/python`,
else `python3`), runs the renderer, and writes the **16:9** cut
(`out/voice_race.mp4` + `.gif`) and the **1:1 square** cut
(`out/voice_race_square.mp4` + `.gif`). No Docker, no Xvfb, just real clips,
Pillow, and ffmpeg. Knobs: `VOICE_REPO`, `PYTHON`, `FPS`, `GIF_FPS`; the renderer
also takes `--fixtures/--spec/--logo/--out/--cli/--model` directly.

## The technique (reusable for ANY "engine A vs engine B" comparison)

This is the part to steal. The renderer is ~450 lines of Pillow; the shape is
generic and the engine-specific bits are isolated into a few **swap-seams**.

### 1. Drive BOTH engines for real, off-screen

The race does not time anything at render time. The real work happens **once**, in
a tiny measurement script that drives **both** engines and writes `spec.json`:

```python
# voice-detect.cpp/benchmarks/demo/measure_voice.py (the two CLI calls = swap-seam)
ggml_ms = voicedetect_cli("bench", "--mode", "embed", "--threads", "8")   # the .cpp engine
onnx_ms = onnxruntime_session.run(...)                                     # the reference
```

`measure_voice.py` interleaves ggml and onnxruntime rounds and takes the **min**
per engine (the run where the scheduler gave it its full cores), so the numbers
are real observed latencies, not load-inflated averages. A verify is two
embeddings, so `verify_ms = 2 * embed_ms`. The render reads `--spec`; regenerate
it from a built checkout with `python .../benchmarks/demo/measure_voice.py`.

### 2. Real inputs only, drawn in both panes

The two clips come from the engine's **in-repo real fixtures**
(`tests/fixtures/clip_a.wav`, `clip_b_same.wav`). `load_wave_env()` reads the WAV
and reduces it to a 150-bin peak envelope; `draw_wave()` paints the center-line
waveform and reveals it left-to-right by the pane's progress. Same two real
waveforms in both panes, so the eye compares engines, not inputs.

### 3. The progress bar fills at the REAL proc-time

Each pane's fill fraction is `min(1, t_real / engine.proc_s)`, where `proc_s` is
that engine's real measured time. The faster engine's bar simply reaches 1.0
first. `--dilate` scales only PLAYBACK (a ~30 ms race is watchable in ~11 s); it
never changes the *ratio* between the two bars, so the relative finish is honest.

### 4. Reveal each engine's real output, then the shared verdict

While racing, a pane shows `comparing embeddings ...` and a live ms counter. When
its bar fills, `pane()` swaps to the revealed result: the green `verdict`, the real
`d=` distance and `threshold` from `spec.json`, the per-engine `verify in N ms`,
and a `bit-exact match` badge. Both panes reach the **identical** verdict, which is
the whole point.

### 5. End on the LocalAI CTA card

`end_card()` shows the **logo** (`localai_logo.png`, configurable via `--logo`),
the team tagline, the honest bit-exact headline, the **on-par bars** (real ggml vs
onnx verify ms), and **four links** (localai.io, the LocalAI repo, the engine repo,
the GGUF repo). Same finish as the `duel`/`face_carousel` outros, drawn instead of
muxed.

### 6. Pillow loop + ffmpeg encode (mp4 + palettegen/paletteuse gif)

Frames are written as `f%05d.png` into a temp dir, then:

```sh
# crisp mp4
ffmpeg -framerate 20 -i f%05d.png -pix_fmt yuv420p out.mp4
# clean gif: build an optimal palette, then apply it (avoids 256-colour banding)
ffmpeg -i out.mp4 -vf "fps=14,scale=900:-1:flags=lanczos,palettegen=stats_mode=diff" pal.png
ffmpeg -i out.mp4 -i pal.png \
  -lavfi "fps=14,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" out.gif
```

The two-pass `palettegen`/`paletteuse` is what keeps the gif from looking like a
2010 gif: a per-clip optimal palette plus light bayer dithering.

### Layout: cols vs square

The 16:9 cut (`race_frame`, 1280x720) lays the two engine panes **side by side**,
best for a README hero or landscape post. The 1:1 cut (`race_frame_square`,
1080x1080) **stacks** them (engine A on top, engine B below) for a feed. Both share
the same `header`, `pane`, progress logic, brandline, and ffmpeg encode; only the
two rect lists and the end-card layout differ. `main()` renders both in one pass.

## The swap-seams (what to edit to retarget)

Four edits, nothing else:

1. **The two engine calls** in the measurement script (`measure_voice.py`): swap
   `voicedetect-cli bench` and the `onnxruntime` session for *your* pair (e.g. a
   `whisper.cpp` CLI vs `faster-whisper`, or a depth `.cpp` CLI vs `torch`). The
   `--cli` / `--model` flags name the binary + weights that produced `spec.json`.
2. **The `spec.json` numbers**: the keys the render reads are
   `ggml_verify_ms`, `onnx_verify_ms`, `distance`, `threshold`, `verdict`,
   `threads`. Rename/extend to your task's real measured fields.
3. **The per-engine pane fields** in `pane()`: the title/device line, the two
   waveforms (swap for a spectrogram, a transcript, a depth map, boxes...), the
   progress-bar source, and the revealed verdict block.
4. **The end-card copy + links** in `end_card()` / `end_card_square()`: the
   headline, the on-par bars, the four links (localai.io + the LocalAI repo stay;
   swap the engine repo + HF weights).

Keep the race logic, the easing-free linear `proc_s` fill, the palette, and the
ffmpeg encode as-is.

## Adapt it to another pair of engines

Pick any "ggml `.cpp` engine vs its reference framework on the same real input"
and the recipe holds:

- **ASR**: `parakeet.cpp` vs NeMo on a real `.wav`. Panes show the waveform +
  the streamed transcript; the verdict becomes the final text + WER vs reference.
- **Depth**: `depth-anything.cpp` vs torch on a real image. Panes show the input +
  the colorized depth; the verdict becomes min/max/median depth.
- **Detect**: `locate-anything.cpp` vs the PyTorch model. Panes show the image
  with boxes drawing in; the verdict becomes the class + score.

If the `.cpp` engine wins on speed, *then* the bars can lead with the ratio. If it
is on par (like this one), keep the honest framing: lead with **bit-exact parity +
zero Python**, and let the duel be the hook, not the claim.

Palette is the shared house dark (`#0d1117` bg, teal accent) so it matches the
other LocalAI `.cpp` demos. No em-dashes in any rendered text.
