# 08 — Detailer / Refiner decoupling patch

A bug in SD.Next's processing pipeline causes the Detailer pass to inherit the
Refine pass's denoising schedule, making `Detailer strength` effectively
non-functional. This repo ships a one-line patch that decouples them.

Applies to SD.Next commit `0eb4a98e0` (2026-04-04) and later, until merged
upstream.

## Symptom

`Detailer strength` slider has little or no observable effect. The face region
is always a hybrid between the model's native face and the Detailer prompt
target, regardless of whether you set strength to 0.3, 0.7, or 1.0. With
Detailer prompt doing an aggressive face swap (e.g. a celebrity LoRA or face
embedding), the result is "face still looks like the original with some
hints of the target" instead of a clean replacement.

You may also notice Detailer step count is inflated relative to the UI value.
UI says 20 steps but the progress bar shows 32 or 80.

## Reproducer

1. Fixed seed, SDXL base + hires + face-yolo8m detailer enabled
2. Set `Refiner start = 0.75` and `Detailer strength = 1.0`
3. Generate; check log for the detailer pass
4. Observe the pipeline kwargs:

```
Detail: pipeline=StableDiffusionXLInpaintPipeline task=INPAINTING
  ... 'denoising_start': 0.75, 'denoising_end': 1, 'strength': 1.0
  'num_inference_steps': 80
Progress: 32/32 Detail
```

`denoising_start=0.75` is the leaked Refiner start value. Because diffusers'
inpaint pipeline uses `denoising_start` when provided, `strength=1.0` is
effectively ignored, and the face is repainted only over the noise range
`[0.75·T, 0]` — about 25% of full range.

Changing `Detailer strength` between 0.3 and 1.0 produces no visible difference
under this coupled state.

## Cause

`modules/processing_diffusers.py:140` sets a flag shared by both refine and
detailer passes:

```python
use_denoise_start = not txt2img and p.refiner_start > 0 and p.refiner_start < 1
```

This flag is later used to compute `denoising_start` / `denoising_end` kwargs
for the diffusers pipeline. It does not distinguish the Detailer pass (which
tags itself via `p.ops.append('detailer')` in `modules/postprocess/yolo.py:409`)
from the Refine pass, so both inherit the refiner's schedule.

A secondary consequence: `calculate_base_steps()` in `processing_helpers.py:461`
inflates `num_inference_steps` by `p.steps // (1 - p.refiner_start)`, producing
the 20 -> 80 step count mismatch seen in the log.

## Fix

One-line change to `processing_diffusers.py:140`:

```python
# Before:
use_denoise_start = not txt2img and p.refiner_start > 0 and p.refiner_start < 1

# After:
use_denoise_start = not txt2img and p.refiner_start > 0 and p.refiner_start < 1 and 'detailer' not in p.ops
```

Refine pass behavior is unchanged (still honors Refiner start). Detailer pass
falls through to the standard `strength`-driven schedule diffusers expects for
inpaint, so `Detailer strength` now maps linearly to repaint intensity.

The patch is in [`patches/detailer-refiner-decouple.patch`](../patches/detailer-refiner-decouple.patch)
as a git-format unified diff, with full context header.

## How to apply

From the root of this repo, with your SD.Next install at `C:\sd_next_a770`:

```bash
python tools/apply_patches.py --dry-run     # check first
python tools/apply_patches.py               # apply all
```

The tool creates `.orig` backups next to each modified file before applying,
and uses `git apply` to ensure clean application. Re-running is a no-op if
the patch is already in the tree.

Custom install path:

```bash
python tools/apply_patches.py --sdnext "D:\sdnext"
```

Single patch only:

```bash
python tools/apply_patches.py --patch detailer-refiner-decouple.patch
```

Restart SD.Next after applying for the change to take effect (Python does
not hot-reload imported modules).

## Revert

```bash
python tools/apply_patches.py --revert
```

Or manually:

```bash
cd C:\sd_next_a770
cp modules/processing_diffusers.py.orig modules/processing_diffusers.py
# or via git
git checkout modules/processing_diffusers.py
```

## Verification

After restart, generate the same reproducer image. The detailer pass log should
show:

```
Detail: ... 'denoising_start': None, 'denoising_end': None, 'strength': 1.0
  'num_inference_steps': 20
Progress: 20/20 Detail
```

`denoising_start: None` confirms the fix. Step count matches the UI value.

Visually: `Detailer strength = 1.0` now produces a full face replacement (may
look too aggressive — the face no longer has an anchor to the body's position
/ angle / scale, which is correct full-repaint behavior). `Detailer strength =
0.5` gives a 50% blend, and so on.

For face-swap use cases, `Detailer strength = 0.5-0.7` typically gives the
best balance between identity transfer and anatomical coherence with the body.

## Related issue not fixed by this patch

`modules/postprocess/yolo.py:371` aliases `detailer_strength` as
`denoising_strength` in the args dict passed to `processing_class.switch_class()`.
`switch_class` at `processing_class.py:880-887` then writes those args back
onto the processing object via `setattr`, permanently mutating
`p.denoising_strength`.

This is harmless with a single detailer model because detailer is the last
pipeline stage, but would cause incorrect behavior with chained detailer
models (e.g. face + eyes + mouth), where each detailer invocation would see
the previous one's strength as its baseline denoising_strength.

Flagged as a follow-up refactor candidate in the patch header. Not addressed
here because it requires deeper changes to the detailer dispatch logic and
the single-detailer case is the overwhelmingly common one on A770 setups
(multi-detailer chains are memory-heavy and rarely used).

## Upstream status

Candidate for submission to [vladmandic/sdnext](https://github.com/vladmandic/sdnext)
as a PR. If merged upstream, this patch becomes unnecessary and should be
removed from the `patches/` directory. Check the CHANGELOG and upstream
commit log before applying against a newer SD.Next version than the one
listed at the top of this doc.
