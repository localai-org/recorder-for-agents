#!/usr/bin/env python3
"""Replay real parakeet.cpp output in sync with the audio, for recording.

  player.py diar  arg_sas.json  --dur 34.2 --note "..."
  player.py scene scene.jsonl   --dur 37.1 --note "..."

diar:  offline speaker-attributed ASR JSON (parakeet_capi_transcribe_and_diarize_json);
       words appear as they are spoken (subtitle-style playback of the result).
scene: parakeet-cli scene --json stream; each document is shown when the stream
       emitted it (its "t"), so the on-screen lag is the real live latency.
"""
import argparse, json, time
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

SPK = ["#f0b429", "#3ec8e0", "#e0607e", "#b48ead"]
SND = "#9ccc65"
DIM = "#6e7681"
INK = "#d7dde5"
SPEECH = {"Speech", "Male speech, man speaking", "Female speech, woman speaking",
          "Child speech, kid speaking", "Conversation", "Narration, monologue",
          "Speech synthesizer"}

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["diar", "scene"])
ap.add_argument("data")
ap.add_argument("--dur", type=float, required=True)
ap.add_argument("--title", default="parakeet.cpp")
ap.add_argument("--note", default="")
ap.add_argument("--foot", default="")
a = ap.parse_args()
con = Console(color_system="truecolor")
W = con.width


def mmss(t):
    return f"{int(t) // 60:02d}:{t % 60:04.1f}"


# ---------------------------------------------------------------- data -> timed events
# Each event: (show_at, kind, payload). Lanes: list of (show_at, lane, start, end).
events, lanes, lane_names = [], [], []
if a.mode == "diar":
    d = json.load(open(a.data))
    for u in d["utterances"]:
        if u["start"] >= a.dur:
            continue
        words = [w for w in d["words"] if u["start"] - 0.01 <= w["start"] <= u["end"] + 0.01]
        events.append((u["start"], "utt", {"speaker": u["speaker"], "words": words}))
        lanes.append((None, f"Speaker {u['speaker']}", u["start"], min(u["end"], a.dur)))
    lane_names = sorted({l[1] for l in lanes})
else:
    for line in open(a.data):
        doc = json.loads(line)
        t = doc["t"]
        for u in doc["utterances"]:
            events.append((t, "utt", {"speaker": u["speaker"], "text": u["text"],
                                      "start": u["start"], "end": u["end"]}))
        for s in doc["speakers"]:
            lanes.append((t, f"Speaker {s['speaker']}", s["start"], s["end"]))
        for s in doc["sounds"]:
            if s["label"] in SPEECH:
                continue
            events.append((t, "snd", s))
            lanes.append((t, "Sounds", s["start"], s["end"]))
        events.append((t, "active", [s for s in doc["active"]["sounds"] if s["label"] not in SPEECH]))
    # speakers seen only as a sound-overlap blip are not interesting on screen
    lane_names = ["Speaker 0", "Speaker 1", "Sounds"]
events.sort(key=lambda e: e[0])


# ---------------------------------------------------------------- rendering
def lane_rows(now):
    cells = W - 16
    out = []
    for name in lane_names:
        color = SND if name == "Sounds" else SPK[int(name.split()[-1]) % len(SPK)]
        row = Text(f" {name:<11} ", style=f"bold {color}")
        for c in range(cells):
            t0 = c * a.dur / cells
            t1 = (c + 1) * a.dur / cells
            on = any(ln == name and (show is None or show <= now) and s < t1 and e > t0
                     and (show is not None or t0 <= now)
                     for show, ln, s, e in lanes)
            if on:
                row.append("█", style=color)
            elif t0 <= now:
                row.append("─", style="#30363d")
            else:
                row.append(" ")
        out.append(row)
    # playhead ruler
    pos = min(int(now / a.dur * cells), cells - 1)
    ruler = Text(" " * 13 + "·" * pos, style=DIM)
    ruler.append("▲", style=f"bold {INK}")
    out.append(ruler)
    return out


def transcript(now):
    lines = []
    active = []
    for show, kind, p in events:
        if show > now:
            break
        if kind == "active":
            active = p
            continue
        if kind == "snd":
            lines.append(Text.assemble(("  ♪ ", SND), (f"{p['label']}", f"bold {SND}"),
                                       (f"  {p['peak']:.2f}   [{mmss(p['start'])} - {mmss(p['end'])}]", DIM)))
            continue
        spk = p["speaker"]
        col = SPK[spk % len(SPK)]
        t = Text.assemble((f"Speaker {spk}  ", f"bold {col}"))
        if "words" in p:
            said = [w["text"] for w in p["words"] if w["start"] <= now]
            t.append(" ".join(said), style=INK)
        else:
            t.append(p["text"], style=INK)
        lines.append(t)
    return lines, active


def frame(now):
    head = Table.grid(expand=True)
    head.add_column(); head.add_column(justify="right")
    head.add_row(Text(a.title, style=f"bold {INK}"), Text(f"{mmss(now)} / {mmss(a.dur)}", style=DIM))
    parts = [head]
    if a.note:
        parts.append(Text(a.note, style=DIM))
    parts.append(Text(""))
    parts += lane_rows(now)
    lines, active = transcript(now)
    if a.mode == "scene":
        hear = Text(" now hearing  ", style=DIM)
        if active:
            for s in sorted(active, key=lambda s: -s["peak"])[:2]:
                hear.append(f" ♪ {s['label'].split(',')[0]} ", style=f"bold black on {SND}")
                hear.append(" ")
        else:
            hear.append("speech", style=DIM)
        parts += [Text(""), hear]
    rows_left = con.height - len(parts) - 6 - (1 if a.foot else 0)
    body = Group(*[x for l in lines for x in (l, Text(""))])
    # keep the newest lines visible: measure rendered height, drop from the top
    while lines:
        h = sum(len(con.render_lines(l, con.options.update(width=W - 4))) + 1 for l in lines)
        if h <= rows_left:
            break
        lines = lines[1:]
    body = Group(*[x for l in lines for x in (l, Text(""))])
    parts.append(Panel(body, border_style="#30363d", height=rows_left + 2))
    if a.foot:
        parts.append(Text(a.foot, style=DIM, justify="center"))
    return Group(*parts)


start = time.monotonic()
with Live(frame(0), console=con, screen=True, refresh_per_second=20, transient=False) as live:
    while True:
        now = time.monotonic() - start
        if now >= a.dur:
            live.update(frame(a.dur))
            break
        live.update(frame(now))
        time.sleep(0.05)
    time.sleep(0.8)
