"""Offline speaker-attributed ASR through the C API (one call: ASR + diarization).

  sas_json.py <libparakeet.so> <asr.gguf> <diar.gguf> <audio_16k_mono.wav> > out.sas.json

Prints parakeet_capi_transcribe_and_diarize_json ({speakers, utterances, words}) and
the load/inference timing on stderr. Build the lib with -DPARAKEET_SHARED=ON.
"""
import ctypes, sys, wave, array, json, time
L=ctypes.CDLL(sys.argv[1]); L.parakeet_capi_load.restype=ctypes.c_void_p; L.parakeet_capi_load.argtypes=[ctypes.c_char_p]
f=L.parakeet_capi_transcribe_and_diarize_json; f.restype=ctypes.c_void_p; f.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_int,ctypes.c_int]
t0=time.time()
a=L.parakeet_capi_load(sys.argv[2].encode()); d=L.parakeet_capi_load(sys.argv[3].encode())
w=wave.open(sys.argv[4]); raw=array.array('h',w.readframes(w.getnframes())); sr=w.getframerate()
pcm=(ctypes.c_float*len(raw))(*[x/32768 for x in raw])
t1=time.time()
p=f(a,d,pcm,len(raw),sr); t2=time.time()
s=ctypes.string_at(p).decode()
print(s); print(f"load {t1-t0:.2f}s infer {t2-t1:.2f}s", file=sys.stderr)
