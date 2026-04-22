# 07 — Troubleshooting

Issues encountered during a year of running SD.Next on Arc A770. Each includes
the symptom, root cause, and fix.

## Triton test fails at startup with `UnicodeDecodeError: 'cp950' codec can't decode byte ...`

**Symptom:** On Traditional Chinese / CJK-locale Windows, SD.Next startup log
shows:
```
WARNING  Triton test fail: UnicodeDecodeError: 'cp950' codec can't decode byte 0xe7 in position 120: illegal multibyte sequence
DEBUG    Triton: pass=False version=None fn=<module>:set_cuda_params time=24.20
```
and startup takes ~20 s longer than expected.

**Cause:** SD.Next's Triton test invokes `torch.compile(fullgraph=True)` which
shells out to a C++ compiler. The output gets decoded using the system ANSI
code page (CP950 on zh-TW Windows) but contains UTF-8 bytes, triggering the
error.

**Fix:** Set Python to UTF-8 mode in the launch bat **before** invoking Python:
```batch
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

After the fix, the Triton test still fails (for unrelated reasons — see below)
but fails in ~3 s instead of ~25 s.

## Triton test fails with `RuntimeError: main.cpp`

**Symptom:** Even after the UTF-8 fix, log shows:
```
WARNING  Triton test fail: RuntimeError: main.cpp
```

**Cause:** `torch.compile`'s Inductor backend needs a C++ compiler in PATH
(MSVC's `cl.exe` or equivalent). On a typical user install without Visual
Studio Build Tools exposed to PATH, this fails.

**Fix:** None needed — this is **expected and harmless**. As of 2026-04,
`torch.compile` on XPU via Inductor is not viable for SDXL anyway; even if
compilation succeeded, the produced kernels are not faster than SDPA.
`triton=fail` in the parameter log is acceptable.

## Black patches or fully black images after hires pass

**Symptom:** Hires output has solid black regions or is entirely black. Detailer
then tries to process the black face and produces garbage.

**Cause:** BF16 NaN propagation in VAE decode. SDXL hires at strength 0.99 can
produce latent values that overflow BF16 range during decode.

**Fix:** `diffusers_vae_upcast: true` in SD.Next settings. VAE runs FP32 for
decode (not just the full-resolution final decode — also for hires decode).

## OOM during hires VAE decode

**Symptom:** Hires pass completes but VAE decode crashes with `torch.xpu.OutOfMemoryError`.

**Cause:** Transient memory spike during VAE decode of hires-size latent.
Default PyTorch XPU allocator fragments memory over long runs until no
contiguous block is available for VAE decode workspace.

**Fix:** Combination of several settings:
- `PYTORCH_XPU_ALLOC_CONF=max_split_size_mb:512` (env var)
- `torch_expandable_segments: true` (SD.Next config)
- `torch_gc_threshold: 80` (SD.Next config — triggers GC before OOM)
- `diffusers_vae_tiling: true` with `tile_size: 1088` (VAE tiled decode)

With all four in place, 270+ image long-run had zero OOM.

## LoRA causes long-run to crash after ~100-500 images

**Symptom:** Without LoRA, 8+ hour runs complete cleanly. With a LoRA loaded,
generation eventually crashes (OOM or Python-level exception) after 1–5 hours
of continuous use with the same LoRA.

**Cause:** Without `lora_fuse_native: true`, SD.Next applies LoRA weights to
UNet every forward pass and reverts afterward. This merge/unmerge cycle
accumulates XPU memory fragmentation.

**Fix:** `lora_fuse_native: true` in SD.Next settings. LoRA weights are
permanently fused into the UNet on load. No per-step merge/unmerge cycle.

**Workflow note:** This works best when you use the same LoRA for a whole
session (which is the typical long-run case). Switching LoRAs between images
triggers unfuse+refuse overhead and partially defeats the stability benefit.

## Detailer produces red / color-shifted faces

**Symptom:** Face detailer output has obviously wrong skin color (often pink
/ red tint), or the face appears a different size from the body.

**Cause:** `control/Refiner start` set outside the range (0, 1). SD.Next maps
this to the detailer's `denoising_start`. If set to 0 or 1 (including the
`None` default when the slider is "inactive"), detailer runs full-repaint
from pure noise instead of partial refine — the detailer has no anchor to
the original face's color / proportions.

**Fix:** Set `control/Refiner start: 0.5` in the UI. Detailer will then run
partial denoise starting at 50% noise + 50% original face.

## SD.Next `Modified files` warning lists the bat's own backup

**Symptom:** Startup warning:
```
WARNING  Modified files: [..., 'modules/ui_definitions.py.bak-20260422-104818']
```

**Cause:** A backup file created by this repo's earlier tooling
(`tools/sdnext_patches.py`) that is tracked as "modified" by SD.Next's git-based
file check. (Current version of this repo does not create such backups.)

**Fix:** Delete the `.bak-*` file. SD.Next only cares about files in its own
directory tree.

## `script_callbacks.py` and similar SD.Next internal warnings

**Symptom:** `WARNING Setting validation: unknown=['detailer_seg', ...]`

**Cause:** Settings from older SD.Next versions that have been removed. Your
`config.json` still has them.

**Fix:** In SD.Next Settings, make any small change and Apply & Save — the
save routine drops unknown keys.

## `has_bfloat16_conversions: False` — am I using the wrong dtype?

See [`06-pipeline-tradeoffs.md`](06-pipeline-tradeoffs.md). Short answer: yes
A770 lacks hardware BF16, but switching to FP16 triggers NaN/black-image
issues in SDXL merge checkpoints. This is a conscious tradeoff.

## Startup takes 2 minutes or more

**Symptom:** Startup time in SD.Next log shows `total=120` or higher.

**Common causes:**
- Triton test UnicodeDecodeError (fix: `PYTHONUTF8=1`)
- First-time model load (legitimate, ~18 s for SDXL)
- Network check for SD.Next updates (normal on first startup of the day)
- Slow disk (if you have checkpoints on a spinning HDD, move to SSD)

Expected total with this repo's config: **~50–85 s**.

## Python process runs on E-cores (Task Manager shows uneven CPU load)

**Symptom:** Task Manager's CPU details view shows Python's threads hopping
between P-cores and E-cores. Pipeline stages like YOLO detection and prompt
parsing are slower than expected.

**Cause:** Windows scheduler does not always pin compute-heavy processes to
P-cores, especially when the system is otherwise idle.

**Fix:** The launch bat uses `start /AFFINITY FFFF` to pin Python to P-cores
(on 14900K / 13900K). Verify in Task Manager → Details → right-click python.exe
→ "Set affinity..." — only CPU 0 through CPU 15 should be checked.

If you have a different CPU, update the `CPU_AFFINITY` variable in the bat
header. See the table in `docs/02-env-vars.md`.

## Generation is fast but whole PC feels sluggish

**Symptom:** With the launch bat running, typing, mouse movement, or background
apps feel laggy.

**Cause:** `/HIGH` priority Python + P-core affinity means Python dominates
CPU time on the P-cores.

**Fix options:**
- Remove `/HIGH` (change to `/NORMAL` or omit the priority flag) in the bat
- Widen `CPU_AFFINITY` to include E-cores (e.g. `FFFFFF` adds 8 more threads)
- Only run generation when you don't need the PC for other tasks

Do **not** use `/REALTIME` priority — it can cause the OS to hang.
