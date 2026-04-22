# 05 — Benchmarks

All numbers measured on the reference machine:

- Intel Core i9-14900K (13900K die)
- Intel Arc A770 16GB, driver 1.13.35227
- 96 GB DDR5 system RAM
- Windows 11 (10.0.26200 build)
- torch 2.11.0+xpu, oneAPI 2025.3, SD.Next commit 0eb4a98e

Measurement mode: **sustained long run** (not first image; not cache-heavy
warmup). All times from SD.Next's own `total` timer unless otherwise noted.

## Pipeline summary

```
Base (16 steps, 768×1088)
  → VAE decode
  → WAN Asymmetric Upscale (1.5×)
  → Hires img2img (12–20 steps, 1152×1632, strength 0.75–0.99)
  → VAE decode
  → Face detailer (13–14 effective steps, 1024×1024)
  → VAE decode
  → Grading + save
```

## Per-stage timing (steady-state, image ~100+ in session)

| Stage | Time | Notes |
|---|---|---|
| Base sampling (16 steps) | 5.2 s | DPM++ 2M Karras, CFG 6, 2.67 it/s |
| Base VAE decode | 0.02–0.07 s | Heavy cache hit with fixed seed |
| WAN Asymmetric upscale | 2.4–3.3 s | Qwen encode → Wan decode (2×) |
| PIL resize to 1152×1632 | 0.06 s | |
| Hires sampling (20 steps) | 14.9 s | 1.34 it/s at 1152×1632, CFG 4.5 |
| Hires VAE decode | 0.15–0.26 s | latents [1,4,204,144] |
| YOLO face detection | 0.27 s | face-yolo8m, after first-time load |
| Detailer sampling (13 eff. steps) | 6.0 s | 2.17 it/s at 1024×1024 |
| Detailer VAE decode | 0.06–1.7 s | [1,4,128,128], varies with cache |
| Grading + PIL paste + PNG save | 2.0 s | |
| **Core compute sum** | **~30–35 s** | |
| **Non-compute (callback + pre + post)** | **~70 s** | Python overhead |
| **Total per image** | **~100–110 s** | |

## Sustained long run (270+ images, random seeds)

| Metric | Value |
|---|---|
| Run duration | 8+ hours |
| Images completed | 270+ |
| Time per image (median) | **106 s** |
| Time per image (std dev) | ± 3 s |
| Peak VRAM (per image, consistent) | **11.24 GB** |
| Hires transient peak (before GC) | ~15.8 GB (~11% of images, GC catches) |
| `retries` count (across all images) | **0** |
| `oom` count (across all images) | **0** |
| RAM used | 28.2 – 28.8 GB (stable) |
| VRAM drift over 8 hours | none |

## A/B: before vs after tuning

Baseline = SD.Next default config, minimum launch args, no env tuning.
This repo = the configuration in `launch/sd_next_a770.bat` + `docs/03-sdnext-settings.md`.

| Metric | Baseline | This repo | Δ |
|---|---|---|---|
| Total per image | ~288 s | ~106 s | **−63%** |
| Base sampling | 1.32 s/it | 2.67 it/s (= 0.37 s/it) | **−72% per step** |
| Hires sampling | 1.98 s/it | 1.34 it/s (= 0.75 s/it) | **−62% per step** |
| VAE decode (hires) | 15.8 s | ~0.25 s (cached) / ~10 s (uncached) | significant |
| Peak VRAM | similar | similar | no regression |
| OOM rate | occasional | zero in 270+ images | stability |

(Baseline numbers from prior sessions before tuning; see memory notes for the
full evolution history.)

## Upscaler comparison

Same base image, same hires settings, only upscaler varied:

| Upscaler | Output | Upscale time | Next-stage VAE-decode needed? | Visual (coser/realistic) |
|---|---|---|---|---|
| ESRGAN 4x NMKD Superscale | 4× then downscale | ~13 s | yes | sharp but hard |
| ESRGAN 4x UltraSharp | 4× then downscale | ~13 s | yes | softer skin |
| RealESRGAN_x2plus | 2× then downscale | 6.7 s | yes | general realistic |
| **WAN Asymmetric Upscale** | 2× via VAE decode | **2.9 s** | **no (combines)** | **best for real-photo** |

WAN Asymmetric Upscale wins on time *and* quality for realistic content because
it replaces both the SDXL VAE decode and the separate upscale step with one
Wan2.1-VAE-based decode-and-upscale operation.

## A770 vs community baselines (approximate)

Reports from various Arc A770 users on Reddit / Civitai discussions (2024–2025
timeframe):

| Benchmark setup | Typical it/s | This repo | Notes |
|---|---|---|---|
| SDXL 1024×1024 base, IPEX default | 1.5 – 2.0 | ~2.0 (extrapolated) | matched or exceeded |
| SDXL 768×1024 base | 2.2 – 2.6 | **2.67** | exceeds typical |
| Hires 1152×1632 img2img | 0.9 – 1.2 | **1.34** | exceeds typical |

## Startup cost

| Phase | Time |
|---|---|
| SD.Next installer + version check | 4 s |
| Package imports + modules | 10–15 s |
| Torch/XPU init + Triton test (now fast, thanks to PYTHONUTF8) | 5 s |
| Model load (SDXL checkpoint) | 18 s |
| Pipeline setup + fuse-qkv | 8 s |
| **Total startup** | **~50 s** |

Amortized across a long run this is negligible — the bat is designed for
one-shot launch and long session.
