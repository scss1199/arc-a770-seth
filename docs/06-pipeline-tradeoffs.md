# 06 — Pipeline tradeoffs

Decisions where this repo chose stability or quality over raw speed, and the
reasoning.

## BF16 instead of FP16

**Choice:** `cuda_dtype: BF16`

**Speed cost:** ~15–30% potential speedup left on the table. A770 has
`has_fp16: True` (hardware supported) but `has_bfloat16_conversions: False`
(software emulated). In pure-compute terms, FP16 would be faster.

**Why chose BF16:**
- FP16 produces NaN → black images in SDXL merge checkpoints with hires img2img
  at strength ≥ 0.9, specifically during the refine pass
- BF16's wider dynamic range (same exponent bits as FP32) prevents overflow
  in attention scores, which is where FP16 typically fails
- The speed lost is fixed; the hours lost cleaning up black-image batches are
  variable and unbounded

**When to reconsider:**
- You're using a model known to be FP16-safe (e.g. original SDXL base from
  StabilityAI without community merges)
- You can validate stability on short runs before committing to long runs
- You've set `no_half_vae: true` to keep VAE in FP32 regardless of UNet dtype

## VAE FP32 upcast (mandatory for hires-refine workflow)

**Choice:** `diffusers_vae_upcast: true`

**Speed cost:** VAE decode ~2× slower than BF16 VAE decode.

**Why non-negotiable here:**
- SDXL hires img2img at strength 0.99 = near full regeneration of the upscaled
  image. The latent space entering VAE decode has more dynamic range than at
  strength < 0.5.
- BF16 VAE decode on this latent produces NaN in some pixels → black patches
  that are very visible and consistently reproducible
- FP32 upcast adds ~5 s per hires VAE decode but eliminates the failure mode

**When to reconsider:**
- You never use hires img2img at strength > 0.7
- You've tested specifically on your model that BF16 VAE is clean across 100+
  images at your max strength

## `offload_mode: none` (keep everything in VRAM)

**Choice:** Keep UNet + VAE + TE all resident in VRAM.

**Speed benefit:** ~10–15% faster than `balanced` offload (no H2D/D2H between
passes).

**Why this works on 16 GB:**
- Pipeline peak VRAM ~11.2 GB leaves 4.8 GB headroom
- We use the same checkpoint for base and refine (not the SDXL refiner model),
  so no model swap overhead
- Hires transient peak does touch ~15.8 GB briefly but GC at 80% threshold
  catches it every time

**When to reconsider:**
- Adding ControlNet (+1–2 GB) or IPAdapter (+1–2 GB) — may push over the edge
- Switching to separate SDXL refiner checkpoint (base + refiner = 2 models loaded)
- Running multiple LoRAs simultaneously
- In these cases, switch to `balanced` and test.

## Disabled caches (all of them)

**Choice:** `IGC_EnableShaderCache=0`, `IPEX_WEIGHT_CACHE=0`,
`SYCL_CACHE_PERSISTENT=0`, `IPEX_XPU_ONEDNN_LAYOUT=OFF`

**Speed cost:** Kernel recompile every session startup (~5–15 s).

**Why:** In 8-hour runs, cache corruption was observed to cause three separate
failure modes (wrong output, OOM, crash). Detection of corruption requires
visual inspection and by then hundreds of images may be wasted. Cleaning caches
after each crash was worse than never using them.

**When to reconsider:**
- You run short sessions (< 1 hour) and are fine with manual cache cleanup
- Future Intel driver versions fix the corruption pattern (watch release notes)

## `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0`

**Choice:** Disable Arc's dedicated copy engine.

**Speed cost:** Slightly slower H2D / D2H transfers for VAE decode output.

**Why:** On long runs, a specific D2H transfer using the copy engine would
stall indefinitely on this machine (symptom: generation hangs mid-pipeline,
must kill Python). Disabling copy engine sends transfers through the compute
engine instead. No such stalls observed afterward.

**When to reconsider:**
- Newer driver fixes the copy engine issue (check driver release notes for
  "copy engine" or "memory transfer" mentions)
- You measure actual slowdown in your workflow and the stall is gone

## Detailer at 1024 resolution

**Choice:** `control/Detailer resolution: 1024` (SDXL's native resolution).

**Alternatives:** 896 (tested safe historically, saves some VRAM) or 960 (middle).

**Why 1024:**
- SDXL was trained at 1024×1024 — running the detailer inpaint at native size
  produces the most faithful facial features
- Measured peak detailer VRAM: 13.7 GB (before GC). Within limits.
- Quality difference vs 896 is visible on close inspection, especially in iris
  detail and skin pore preservation

**When to reconsider:**
- Adding ControlNet to the pipeline pushes VRAM → drop detailer to 960 or 896
- LoRA overhead pushes VRAM → same

## Hires 20 steps instead of 12

**Choice:** `Hires steps: 20`

**Speed cost:** +6 s per image vs 12 steps.

**Why:** DPM++ 2M Karras 3rd-order solver does not fully converge by step 12
for the detail level wanted in realistic coser body shots. 20 steps is near
the knee of the convergence curve — beyond that diminishing returns. 12 steps
produces visible structural errors (shoe heels disconnecting from shoes, fabric
folds wrong).

**When to reconsider:**
- You're doing anime-style content where convergence is less strict
- You accept slight softness for speed

## Refiner start = 0.5 (critical for detailer not to produce red / wrong-size faces)

**Choice:** `control/Refiner start: 0.5`

**Background:** In SD.Next, this value maps to the detailer's `denoising_start`
parameter. If `0 < value < 1`, detailer runs as a partial-denoise refinement
(start from X% noise + original face). Outside that range (0 or 1), detailer
runs full-repaint from pure noise.

**What happens if you change it:** Full-repaint detailer produces:
- Red / color-shifted faces (latent HDR gets applied twice)
- Wrong face proportions (SDXL regenerates in square, mismatch on paste-back)

**This is an easy-to-accidentally-break setting.** If your detailer output
starts looking wrong, check this first.

## WAN Asymmetric Upscale (real photos) vs ESRGAN

**Choice:** `WAN Asymmetric Upscale` for realistic photo content.

**Speed benefit:** ~10 s saved per image vs 4× ESRGAN + downscale chain.

**Quality benefit:** Wan2.1-VAE finetune trained on real photos. Strong on
skin detail and hair. Does NOT suit anime / lineart / text.

**Drawbacks:**
- First-time download: ~1.5 GB total (Qwen VAE encoder + Wan VAE decoder)
- Replaces the SDXL VAE decode for hires (architectural, not additive)
- Not universally better than 4× ESRGAN for non-photo content

**When to reconsider:** For anime content use `2xLexicaRRDBNet_Sharp` (trained
on Lexica dataset of AI-generated images) or `ESRGAN 4x UltraSharp` (general
purpose).

## What was tried and rejected

| Experiment | Result | Verdict |
|---|---|---|
| v2 Level Zero adapter (`SYCL_UR_USE_LEVEL_ZERO_V2=1`) | VAE decode 2.5 s faster, but callback 2× slower; net worse | Rejected |
| HyperTile UNet | 15–20% faster but tile-boundary quality cost visible | Rejected in favor of `fuse_projections` which recovers the same speedup without quality cost |
| `torch.compile` with IPEX backend | Compilation fails on Windows / no MSVC path in PATH | Not viable as of 2026-04 |
| Latent upscaler (`Latent`) | Much faster (~0 s) but produces weird artifacts in faces | Rejected for realistic content |
| Lanczos / PIL resize then hires | Fastest but hires must regenerate all detail, not good enough | Rejected for realistic content |
| Increasing `max_split_size_mb` to 1024 | No speedup, increased fragmentation overhead | Kept 512 |
| `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=1` | Long-run D2H stall reappeared | Kept at 0 |
