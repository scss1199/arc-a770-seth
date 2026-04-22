# Changelog

## v1.0 — 2026-04-23

Initial public release. Stable configuration distilled from one year of
continuous tuning on Intel Arc A770 16GB + i9-14900K + Windows 11.

### Validated

- 8+ hour continuous long-run, 270+ images with random seeds
- Zero OOM, zero retries
- 11.24 GB peak VRAM (no drift over session)
- Base 2.67 it/s at 768×1088, Hires 1.34 it/s at 1152×1632

### Stack tested

- torch 2.11.0+xpu
- intel-sycl-rt 2025.3.2
- oneAPI 2025.3 (venv) / 2025.2 (system)
- SD.Next commit 0eb4a98e0 (2026-04-04)
- Intel Arc driver 1.13.35227
- Windows 11 build 10.0.26200

### Key environment variables

- `PYTHONUTF8=1` — fixes Triton UnicodeDecodeError on CJK Windows
- `PYTORCH_XPU_ALLOC_CONF=max_split_size_mb:512`
- `SYCL_PI_LEVEL_ZERO_REUSE_DISCARDED_EVENTS=1` — event pool reuse
- All Intel GPU caches disabled (stability choice)
- CPU affinity `FFFF` + HIGH priority (P-core binding on 14900K)

### Known limitations / tradeoffs documented

- BF16 chosen over FP16 (A770 lacks hardware BF16 conversions, but FP16 causes
  NaN/black images in SDXL merge checkpoints)
- VAE FP32 upcast mandatory for hires at strength 0.99
- Intel GPU caches disabled (stability over ~10 s startup gain)
- v2 Level Zero adapter tested but rejected (faster VAE, slower callback)
- `torch.compile` / Triton not viable on XPU for SDXL as of 2026-04
