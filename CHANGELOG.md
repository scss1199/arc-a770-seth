# Changelog

## v1.2 — 2026-04-23

Two reference docs distilled from a private SD.Next settings spreadsheet the
author had been maintaining alongside the year of tuning.

### New

- [`docs/10-sdnext-ui-full-reference.md`](docs/10-sdnext-ui-full-reference.md) —
  **Exhaustive, page-by-page enumeration of every parameter** in SD.Next's
  Settings UI (Model Loading, Offloading, Quantization, VAE, Text Encoder,
  Compute, Backend, Pipeline Modifiers, Compile, Paths, Image Options, Live
  Previews, Postprocessing, Huggingface, Networks, Extensions). Each parameter
  is marked 🔴 critical / 🟡 recommended / ⚪ default-ok / 🟢 don't-touch.
  Values reflect the author's **current live `config.json`** as of this
  release (some tweaked over the course of tuning — see 03 / 06 for the
  rationale trail).
- [`docs/11-prompt-framework.md`](docs/11-prompt-framework.md) —
  **Six-block multi-stage prompt architecture** (`mpp` / `mnp` / `rpp` / `rnp` /
  `dpp` / `dnp`) for demanding composite SDXL pipelines. Formatting rules
  (no-space-after-comma, `BREAK` adjacency, underscore-joined concepts,
  broad-to-narrow ordering), example skeleton, common failure modes + fixes,
  and relationship to the `Refiner start` setting that controls detailer
  behavior.

### Minor

- README navigation updated to include docs 10 and 11.
- Clarified that README's "Prompt examples out of scope" applies to specific
  prompts — the *architecture* (doc 11) is documented.

## v1.1 — 2026-04-23

Added `patches/` infrastructure and the first patch: a one-line fix that
decouples SD.Next's Detailer pass from the Refiner pass's denoising schedule,
making `Detailer strength` functional for the first time.

### New

- `patches/detailer-refiner-decouple.patch` — fix for
  `modules/processing_diffusers.py` where `p.refiner_start` leaked into the
  detailer pass's `denoising_start`, causing `Detailer strength` to have no
  observable effect regardless of UI value
- `tools/apply_patches.py` — applies/reverts patches against the user's
  SD.Next install with automatic `.orig` backup via `git apply`
- `docs/08-detailer-refiner-fix.md` — full root-cause analysis, reproducer,
  and before/after log evidence

### Discovered during

Production use on A770 + SDXL Illust merge + face-yolo8m detailer. Symptom
was that `Detailer strength` slider was inert: moving it 0.3 -> 0.7 -> 1.0
produced visually identical output. Root cause traced to
`processing_diffusers.py:140` where `use_denoise_start` flag was computed
without checking `p.ops` for the detailer pass.

### Known follow-up

`modules/postprocess/yolo.py:371` + `processing_class.py:880` mutate
`p.denoising_strength` via `switch_class`'s post-init setter loop. Harmless
with a single detailer model, would break chained detailers. Flagged in
patch header, not fixed here.

### Upstream

Candidate for PR submission to vladmandic/sdnext. Patch directory will be
pruned as patches get merged upstream.

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
