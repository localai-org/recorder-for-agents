"""Turn `parakeet-cli scene --json` output (one document per step, one pass of
ASR + diarization + sound tags) into the two files render_film.py reads.

  scene2sas.py <scene.jsonl> <offset_seconds> <out.sas.json> <out.sounds.json>

offset_seconds shifts excerpt time back to film time (the excerpt starts at t0).
"""
import json, sys
src, off, out_sas, out_snd = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
utts, words, sounds = [], [], []
for l in open(src):
    d = json.loads(l)
    for u in d["utterances"]:
        utts.append(dict(u, start=u["start"] + off, end=u["end"] + off))
    for w in d["words"]:
        words.append(dict(w, start=w["start"] + off, end=w["end"] + off))
    for s in d["sounds"]:
        sounds.append(dict(s, start=s["start"] + off, end=s["end"] + off))
json.dump({"utterances": utts, "words": words}, open(out_sas, "w"))
json.dump(sounds, open(out_snd, "w"))
print(src, len(utts), "utterances", len(words), "words", len(sounds), "sounds")
