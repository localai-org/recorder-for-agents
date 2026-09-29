# Speaker diarization speed: parakeet.cpp vs NVIDIA NeMo

Model: nvidia/Nemotron-3-Diarization (Sortformer, 8 speakers), default checkpoint
mode on both engines (cache-aware streaming, 264-step / 21.12 s chunks,
speaker cache 264). ASR for the combined run: nvidia/parakeet-tdt_ctc-110m.

Numbers are inference only (model load excluded), median of all timed runs
across passes, "x RT" = audio seconds / inference seconds.

## 12.3 min, 3 speakers (738 s)

| Device | Engine | Precision | Diarization | x RT | Diarization + ASR | x RT |
|---|---|---|---|---|---|---|
| GB10 GPU | parakeet.cpp | F16 | 1.84 s | 402x | 3.27 s | 226x |
| GB10 GPU | parakeet.cpp | Q8_0 | 1.56 s | 474x | | |
| GB10 GPU | NeMo | FP32 | 1.80 s | 410x | 3.50 s | 211x |
| GB10 GPU | NeMo | BF16 autocast | 1.14 s | 648x | | |
| GB10 GPU | NeMo | FP16 autocast | 1.15 s | 641x | | |
| Ryzen 9 9950X3D, 16 threads | parakeet.cpp | F16 | 5.08 s | 145x | 11.78 s | 63x |
| Ryzen 9 9950X3D, 16 threads | parakeet.cpp | Q8_0 | 6.47 s | 114x | | |
| Ryzen 9 9950X3D, 16 threads | NeMo (default) | FP32 | 14.57 s | 51x | 26.43 s | 28x |
| Ryzen 9 9950X3D, 16 threads | NeMo + compiled attention (not default on CPU) | FP32 | 7.57 s | 97x | | |
| Ryzen 9 9950X3D, 8 threads | parakeet.cpp (default threads) | F16 | 5.83 s | 127x | 12.14 s | 61x |
| Ryzen 9 9950X3D, 8 threads | NeMo (default) | FP32 | 13.97 s | 53x | 25.59 s | 29x |
| Ryzen 9 9950X3D, 8 threads | NeMo + compiled attention (not default on CPU) | FP32 | 6.84 s | 108x | | |

## 68.5 s, 2 speakers

| Device | Engine | Precision | Diarization | x RT |
|---|---|---|---|---|
| GB10 GPU | parakeet.cpp | F16 | 0.146 s | 469x |
| GB10 GPU | parakeet.cpp | Q8_0 | 0.137 s | 502x |
| GB10 GPU | NeMo | FP32 | 0.182 s | 377x |
| GB10 GPU | NeMo | BF16 autocast | 0.142 s | 483x |
| CPU, 16 threads | parakeet.cpp | F16 | 0.451 s | 152x |
| CPU, 16 threads | NeMo (default) | FP32 | 1.371 s | 50x |
| CPU, 16 threads | NeMo + compiled attention | FP32 | 0.692 s | 99x |

## Output agreement (10 ms frames, best speaker permutation)

| Pair (12.3 min) | Speech frames | All frames |
|---|---|---|
| GPU: NeMo FP32 vs parakeet.cpp F16 | 99.89% | 99.89% |
| GPU: NeMo FP32 vs parakeet.cpp Q8_0 | 99.80% | 99.81% |
| GPU: NeMo FP32 vs NeMo BF16 autocast | 99.67% | 99.68% |
| GPU: NeMo FP32 vs NeMo FP16 autocast | 99.77% | 99.78% |
| CPU: NeMo FP32 vs parakeet.cpp F16 | 99.95% | 99.95% |
| CPU: NeMo FP32 vs parakeet.cpp Q8_0 | 99.73% | 99.74% |
| NeMo GPU FP32 vs NeMo CPU FP32 | 99.91% | 99.91% |
| parakeet.cpp GPU F16 vs parakeet.cpp CPU F16 | 99.89% | 99.89% |

On the 68.5 s clip parakeet.cpp F16 matches NeMo FP32 on 100% of frames (GPU and
CPU). The combined run's ASR words: 2 word differences out of 2179 vs NeMo on
GPU, 0 on CPU.

## Method

- parakeet.cpp master 6dea76a (ggml v0.13.0), called through the flat C-API
  (`parakeet_capi_diarize_pcm`, `parakeet_capi_transcribe_and_diarize_json`)
  from Python ctypes. NeMo main cf724ac33 (3.1.0), `model.diarize(audio=[array],
  sample_rate=16000, batch_size=1)` with its default config, and for the combined
  run `diarize()` then `transcribe([array], timestamps=True)` back to back.
- Each engine in its own process. Model load timed separately. Each pass: 1
  warmup, then 3 timed runs of one call with the PCM already in memory
  (`time.perf_counter`; on GPU `torch.cuda.synchronize()` before and after each
  NeMo call). The reported value is the median of all timed runs across passes
  (GPU: 3 passes for parakeet.cpp, 2 for NeMo; CPU: 2 to 4 passes). Per-run
  times, min/max and per-pass medians are in results.json.
- GPU: NVIDIA GB10, driver 580.173.02.
  parakeet.cpp built with CUDA 13.0 (sm_121). NeMo on torch 2.11.0+cu128.
- CPU: AMD Ryzen 9 9950X3D devbox (20 vCPUs visible), torch 2.14.0+cpu,
  parakeet.cpp built with -march=native, OpenMP.
- ASR for NeMo uses local attention [128,128], because parakeet.cpp switches to
  the same local attention automatically above 8192 encoder frames (this clip
  has about 9225).

## Caveats

- GPU diarization is a tie at full precision: NeMo FP32 1.80 s, parakeet.cpp
  F16 1.84 s. NeMo with BF16/FP16 autocast is 1.6x faster than parakeet.cpp F16
  (1.14 s vs 1.84 s) and still agrees 99.7% with its FP32 output. parakeet.cpp
  wins the short clip (0.146 s vs 0.182 s FP32, a tie with BF16) and the
  combined diarization + ASR run by about 7%. Do not present the GPU
  diarization-only race as a parakeet.cpp win.
- NeMo on CPU does not compile its flex_attention (NeMo only calls
  torch.compile on CUDA, so CPU runs the unfused implementation). Forcing the
  compiled version halves NeMo's CPU time. The "NeMo (default)" rows are what a
  user gets out of the box; the "compiled attention" rows are a best-effort
  NeMo and parakeet.cpp is still 1.35x to 1.5x faster than those.
- Threads: with 20 threads (all visible vCPUs) PyTorch was pathologically slow
  on this shared box (68.5 s clip: 40 s instead of 1.3 s; 12.3 min: about
  430 s per run), so CPU is reported at 16 threads (the 9950X3D's physical core
  count) for both engines, plus 8 threads (parakeet.cpp's default). NeMo is
  fastest at 8 threads, parakeet.cpp at 16.
- The CPU box is shared with other agents (builds, other parakeet.cpp jobs).
  Each run waited for no foreign process above 30% CPU, but short spikes still
  happened; they show up as outliers in the max column (for example a 12.25 s
  Q8_0 run), which is why medians are pooled over passes. CPU run-to-run
  variance is about 10%. The first CPU attempt at load 27 and a NeMo run at
  load 44 were discarded.
- parakeet.cpp Q8_0 is slower than F16 on this CPU and faster on GPU.
- parakeet.cpp F16 GGUF vs NeMo FP32 weights: parakeet.cpp's weights are half
  precision, NeMo's are full precision (the default). The GPU and CPU torch
  versions differ (2.11 cu128 vs 2.14 cpu); both run the same NeMo commit.
- NeMo CPU ASR load time includes extracting the .nemo to a NAS temp dir (the
  devbox root disk was full), so ignore that load number.
- The combined NeMo timing has no word-to-speaker merge step; parakeet.cpp's
  includes it (it costs microseconds).
