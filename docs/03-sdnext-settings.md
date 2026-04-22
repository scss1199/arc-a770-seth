# 03 — SD.Next UI / config settings

Settings inside `config.json` that were deliberately chosen different from
upstream defaults, and why. Edit via **SD.Next → Settings** then Apply & Save.

## Compute Settings

| Key | Value | Default | Rationale |
|---|---|---|---|
| `cuda_dtype` | `BF16` | `Auto` | BF16 is more numerically stable than FP16 for SDXL merge checkpoints. A770 has no hardware BF16 conversion (see `04-a770-hardware-notes.md`) so this costs some speed, but FP16 produces NaN/black images in this stack. |
| `diffusers_generator_device` | `CPU` | `GPU` | CPU generator gives cross-platform seed determinism and avoids XPU-side RNG overhead at the start of every step. |
| `attention_slicing` | `Disabled` | `Default` | VRAM is sufficient on 16 GB for 768×1088 → hires 1.5× without slicing. Slicing would slow attention ~5–10%. |
| `sdp_options` | `["Memory", "Math"]` | dynamic | Flash attention is not available on XPU. These two kernels are what SDPA falls back to. |
| `xformers_options` | `[]` | `['Flash attention']` | xformers has no XPU build. Clear the flag to avoid fruitless discovery. |

## Backend Settings

| Key | Value | Default | Rationale |
|---|---|---|---|
| `torch_expandable_segments` | `true` | `false` | Allow memory segments to grow as needed. Pairs with `PYTORCH_XPU_ALLOC_CONF=max_split_size_mb:512` in the bat. |
| `torch_gc_threshold` | `80` | `70` | Trigger Python GC + `torch.xpu.empty_cache()` when GPU utilization passes 80%. Slightly later than default → fewer interruptions. |
| `diffusers_fuse_projections` | `true` | `false` | Fuse UNet Q/K/V projection matmuls into one matmul. **~1–3% speedup, zero quality cost.** Costs ~300 MB extra VRAM for the fused weights. |

## Model Offloading

| Key | Value | Default | Rationale |
|---|---|---|---|
| `diffusers_offload_mode` | `none` | `balanced` (on 16 GB) | Keep everything in VRAM. Only viable because we use the same checkpoint for base and refine (Refine pass = hires img2img with same model). |
| `diffusers_offload_always` | `""` (empty) | `VAE` | Default offloads VAE between decode calls, which wastes 1–2 s per image on H2D/D2H. Empty string keeps VAE resident. |
| `models_not_to_offload` | `UNet` | `""` | Explicit pin of UNet to GPU even if offloading re-enables. |

## Variational Auto Encoder

| Key | Value | Default | Rationale |
|---|---|---|---|
| `diffusers_vae_upcast` | `true` | `default` | **Non-negotiable.** SDXL hires img2img at strength 0.99 produces black patches from BF16 NaN propagation in VAE decode without FP32 upcast. |
| `diffusers_vae_tiling` | `true` | depends | Needed to VAE-decode 1152×1632 on 16 GB without memory spikes. |
| `diffusers_vae_tile_size` | `1088` | `0` (auto) | 1088 × 1088 tile with 0.125 overlap covers image width (1152 < 1088+136×2) in one horizontal tile, so only one vertical seam. Carefully chosen for the output resolution. |
| `diffusers_vae_tile_overlap` | `0.125` | `0.25` | Halved from default to save some compute. If visual seams appear, raise to 0.2. |
| `diffusers_vae_slicing` | `true` | `true` | Saves a bit more VAE VRAM. Was once disabled on this machine due to an older IPEX OOM bug but has since been safely re-enabled under the current stack. |

## Pipeline Modifiers (advanced)

| Key | Value | Default | Rationale |
|---|---|---|---|
| `hypertile_unet_enabled` | `false` | `false` | Initially experimented with; disabled after switching to `diffusers_fuse_projections=true`, which recovers the same speedup without the tile-boundary quality cost. |
| `teacache_enabled` | `true` | `false` | TeaCache skips some timesteps via L1 similarity test. ~5% speedup, negligible quality change for SDXL. |
| `teacache_thresh` | `0.10` | `0.15` | More aggressive skipping. Drop to 0.15 if detail looks soft. |
| `tome_ratio` + `todo_ratio` | `0.3` each | `0.0` | Token merging. ToMe + ToDo together give small speedup at mild quality cost. Note: only one of ToMe/ToDo applies at a time depending on which you pick in `token_merging_method`. |
| `hidiffusion_raunet` / `hidiffusion_attn` | `false` | `true` | HiDiffusion modifies UNet structure. Conflicts with custom SDXL merge checkpoints. Leave off. |

## LoRA / Networks

| Key | Value | Default | Rationale |
|---|---|---|---|
| `lora_fuse_native` | `true` | `true` | Fuses LoRA weights into UNet on load rather than applying every step. **Critical for long-run stability** — prevents the repeated merge/unmerge cycle from fragmenting XPU memory over thousands of images. |
| `lora_in_memory_limit` | `1` | `1` | Keep only the currently-used LoRA cached. Reducing this from a larger number (e.g. 10) saves VRAM if you don't hot-swap LoRAs frequently. |

## Compile

| Key | Value | Default | Rationale |
|---|---|---|---|
| `cuda_compile` | `[]` (empty) | `[]` | **Leave empty.** `torch.compile` on XPU via inductor backend is immature as of 2026-04; enabling it can break the pipeline. If you ever want to benchmark, test with `Model` alone. |
| `cuda_compile_backend` | `inductor` | `inductor` | Only relevant if `cuda_compile` is non-empty. `ipex` backend would need the IPEX pip package (not installed here). |

## What NOT to change

- `diffusers_vae_upcast` — keep `true` or you will get black images.
- `lora_fuse_native` — keep `true` or LoRA long-run will crash.
- All the "disabled caches" settings correspond to env-var-level cache disables
  in the bat; keep them consistent.

## Full `config.json` diff tool

Use [`../tools/sdnext_config_diff.py`](../tools/sdnext_config_diff.py) to compare
your live `config.json` against SD.Next's `ui_definitions.py` defaults:

```bash
source /path/to/sdnext/venv/Scripts/activate
python tools/sdnext_config_diff.py
```

Produces a grouped list of every setting you have changed from default, useful
for auditing your own install vs this reference configuration.
