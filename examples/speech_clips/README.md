# speech_clips: launch clips for speech AI (captions on real film, a speed race, an end card)

The scripts behind the parakeet.cpp launch videos: speaker-labelled captions and sound
tags burned onto a Blender open movie, a CPU speed race against NeMo, and an end card that
explains what the project is. Every frame is drawn with Pillow and stitched with ffmpeg
(the same approach as [`image_race`](../image_race)), so it needs no Docker, Xvfb or
display. The only recorder-based piece is `terminal_player.py`, for terminal clips.

All on-screen text and numbers come from real output. Nothing is typed in by hand.

## What is here

| file | what it does |
|---|---|
| `render_film.py` | film excerpt + speaker words + sound events, square or 9:16, with the film's own audio |
| `race.py` | two engines fill the same speaker timeline at their measured speed, then a results card |
| `endcard.py` | animated "what is this" card: name, what it does, links, team logo |
| `finish.sh` | crossfades a clip into the end card (fixed output length, audio fades out) |
| `make_film_clip.sh`, `make_race_clip.sh` | one command per clip type, both layouts |
| `scene2sas.py` | `parakeet-cli scene --json` output to the two files `render_film.py` reads |
| `sas_json.py` | offline ASR + diarization through the C API (ctypes) |
| `terminal_player.py` | replays scene or diarization output in a `rich` TUI, for `record.sh` |
| `fetch_fonts.sh` | downloads Space Grotesk and JetBrains Mono (OFL) into `fonts/` |
| `data/` | the measured benchmark numbers and speaker segments the race uses |

Needs: Python 3 with Pillow, ffmpeg, DejaVu Sans Bold (for the note glyph in the sound chips).
Run `./fetch_fonts.sh` once.

## Film clips

1. Get a film under a licence that lets you show it, and its audio as 16 kHz mono WAV:

   ```sh
   ffmpeg -i film.mp4 -map 0:a:0 -ac 1 -ar 16000 film.wav
   ffmpeg -ss 214 -to 252 -i film.wav excerpt.wav          # the scene you want
   ```

2. Run the models in one pass (ASR + diarization + sound tags in a single stream) and
   convert the result. The offset is the excerpt start, so times line up with the film:

   ```sh
   parakeet-cli scene --model asr.gguf --diar diar.gguf --sound ced-base-q8_0.gguf \
       --latency model --show-speech --json --input excerpt.wav > scene.jsonl
   ./scene2sas.py scene.jsonl 214 work/cosmos.sas.json work/cosmos.sounds.json
   ```

   `--show-speech` keeps the plain Speech and Music tags, so nothing is hidden on screen.

3. Render both layouts and crossfade into the end card:

   ```sh
   ./make_film_clip.sh cosmos film.mp4 214 252 \
     "ASR + speakers + sound tags, one pass, 38 s scene: 1.9 s on a CPU" \
     "Film: Cosmos Laundromat (CC BY 4.0) Blender Foundation | studio.blender.org"
   ```

   Put a measured time in the footer. Time the `scene` run on a quiet machine, model load
   included, and use that number.

The launch clips used these excerpts (film seconds):

| film | excerpt | licence |
|---|---|---|
| Cosmos Laundromat: First Cycle | 214 to 252 | CC BY 4.0 |
| Sintel | 128 to 176 | CC BY 3.0 |
| Sprite Fright | 236 to 268 | CC BY 4.0 |
| Tears of Steel | 2.6 to 45.3 | CC BY 3.0 |

The credit line is burned into every frame. Keep it, and do not edit the film's audio.

## Speed race

```sh
./make_race_clip.sh          # reads ./data, writes out/race_cpu_{square,vertical}.mp4
```

Set `RACE_DATA` to point at another folder (the film wrapper uses `DATA` for its own files,
so the two are separate). `data/` holds the diarization benchmark the launch clip used: 12.3 min, 3 speakers,
Nemotron-3-Diarization, both engines on the same Ryzen 9 9950X3D at 16 threads, inference
only. `pkcpp_cpu.json` and `nemo_cpu.json` set each side's finishing time, so the bars
move at the real speed with no speed-up. `BENCH_RESULTS.md` has the full method and the
GPU table. To race something else, replace the two trace files and the two segment files.

Be straight about the comparison on the card. Here NeMo's CPU default runs unfused
attention, so the card also shows its compiled-attention time (`--compiled-s`), and on
the GPU the two engines tie at full precision, which is stated as well.

## End card

`endcard.py` has the text (name, tagline, three capability lines, links) as constants at
the top. Edit them for another project. `--layout vertical` gives 9:16. Credit the source
of each capability there: for the launch clips the lines read NVIDIA Parakeet, NVIDIA
Nemotron-3-Diarization and Xiaomi CED via ced.cpp.

## Command cards

`cards/*.html` are still images of the commands, in the house dark style (rendered with the
repo's `render-card.sh`, 1200x675 at 2x):

```sh
cd examples/speech_clips
WIDTH=1200 HEIGHT=675 ../../render-card.sh cards/scene_command.html cards/scene_command.png
```

`scene_command` shows the `parakeet-cli scene` line plus real output (trimmed with `...`, one
line with an expletive left out); `localai_install` shows the gallery one-liner and the two
`curl` calls, with no response, because the gallery entries were unreleased when it was made.
Do not paste a fabricated response into it. Edit the HTML and re-render for other commands.

## Terminal clips

`terminal_player.py` replays the same data in a `rich` TUI; record it with the recorder:

```sh
WORK=$PWD BG="#0d1117" FG="#d7dde5" FONTSIZE=21 WIDTH=1080 HEIGHT=1080 DURATION=40 \
  ../../record.sh "python3 terminal_player.py scene scene.jsonl --dur 37.1 --title 'parakeet.cpp'" out.mp4
```

`diar` mode takes the JSON from `sas_json.py`. Trim the dead lead-in with
`../duel/trim_lead.sh`.

## Gotchas found while making these

- Film audio can be 5.1. Downmix to stereo (`-ac 2`) or the AAC encoder refuses it.
- A source MKV can carry a chapter track that ffmpeg copies into the MP4 as a data stream,
  which makes some players reject the file. Pass `-map_chapters -1 -map_metadata -1`.
- An `xfade` plus padded audio with `-shortest` never ends. `finish.sh` sets `-t`
  from the two durations instead.
- Sound tags come from a 3 s window scored once a second, so boundaries sit on a one second
  grid, and plain Speech scores far above the gendered speech labels on cartoon voices.
- Any aspect ratio works: the film is scaled to cover its region and cropped a little above
  centre, so 4:3 films (old public-domain features) are cropped rather than covering the
  captions. The crop is a judgement call; look at a frame before committing to a clip.
- With many speakers the lanes shrink to stay above the footer (tested with five).
- Show at most four chips at once, or a multi-label burst (Insect, Fly, Bee) covers the film.
