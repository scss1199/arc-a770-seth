# 10 — SD.Next UI full parameter reference

This is an exhaustive enumeration of every parameter exposed by SD.Next's
**Settings** panel, organized by page, with annotations on which matter for
Intel Arc A770 + SDXL workflows.

The recommended values here have been validated under **demanding composite
SDXL prompts** — the kind of multi-focus, multi-block compositions (characters
+ costumes + props + environment + anatomical correctness all at once) that
typically fall apart under looser configurations. If you're pushing SDXL to
its limits with multi-stage pipelines, this reference is tuned for that class
of work.

## Legend

- 🔴 **Critical** — must change from default for Arc A770 long-run stability or speed
- 🟡 **Recommended** — should change, noticeable quality / perf gain
- ⚪ **Default OK** — leave as SD.Next default unless you have a specific reason
- 🟢 **Don't touch** — keep at shown value; changing will break stability

See also:
- [03-sdnext-settings.md](03-sdnext-settings.md) for the condensed high-priority list
- [02-env-vars.md](02-env-vars.md) for the env-var layer that pairs with many of these

## Data source

Values in this reference reflect the current live `config.json` of the author's
production install as of this repo's CHANGELOG date. Some values were tweaked
over the long tuning arc; the rationale for every non-default choice lives in
[03-sdnext-settings.md](03-sdnext-settings.md) and
[06-pipeline-tradeoffs.md](06-pipeline-tradeoffs.md).

To compare your own install against this reference, run:
```bash
python tools/sdnext_config_diff.py
```
See [`tools/sdnext_config_diff.py`](../tools/sdnext_config_diff.py).

---

## Model Loading

| Setting | Value / Note | Mark |
|---|---|---|
| Model pipeline | `Autodetect` | ⚪ |
| Refiner model | `None` (we use same base checkpoint for refine pass) | ⚪ |
| UNET model | `Default` | ⚪ |
| Latent history size | `16` | ⚪ |
| Model auto-load on start | `True` | ⚪ |
| Model load using multiple threads | `True` | ⚪ |
| Model auto-download on demand | `True` | ⚪ |
| Model load using streams | `True` | 🟡 faster startup |
| Model load model direct to GPU | `True` | 🟡 |
| Diffusers load using Run:ai streamer | `False` | ⚪ |
| Transformers load using Run:ai streamer | `False` | ⚪ |
| Force model eval | `True` | 🟡 |
| Model load device map | `gpu` | 🟡 (options: default / gpu / cpu) |

## Model Options

| Setting | Value | Mark |
|---|---|---|
| Enable modular pipelines (experimental) | `False` | ⚪ |
| Google Cloud / Vertex AI options | all off | ⚪ |
| Disable T5 text encoder (SD 3.x) | `False` | ⚪ (irrelevant for SDXL) |
| HiDream LLama repo | `Default` | ⚪ |
| WanAI processing stage | `low noise` | ⚪ |
| Stage boundary ratio | `0.85` | ⚪ |
| ChronoEdit temporal steps | `0` | ⚪ |
| Qwen layered number of layers | `2` | ⚪ |

## Model Offloading 🔴

One of the most important pages for performance on 16 GB Arc.

| Setting | Value | Mark |
|---|---|---|
| Model offload mode | **`none`** | 🔴 keep everything in VRAM |
| Non-blocking move operations | `False` | ⚪ (only matters if offload ≠ none) |
| Offload during pre-forward | `False` | 🟡 |
| Offload using streams | `False` | ⚪ |
| Offload low watermark | `0.4` | ⚪ |
| Offload GPU high watermark | `0.8` | ⚪ |
| Model types not to offload | **`UNet`** | 🟡 |
| Modules to always offload | **`""` (empty)** | 🔴 default is `VAE`; empty keeps VAE resident → faster decode |
| Modules to never offload | `""` | ⚪ |
| Group offload type | `block_level` | ⚪ |
| Offload blocks | `0` | ⚪ |

## Model Quantization

Not used in this reference configuration. SDXL quality-first workflows don't
benefit from INT8 / NF4 — they lose facial identity and skin tone fidelity.

| Setting | Value | Mark |
|---|---|---|
| Quantization enabled (SDNQ / Nunchaku / BitsAndBytes / Quanto / TorchAO / TensorRT) | **all `None`** | ⚪ |
| Layerwise casting enabled | `None` | ⚪ |

SDNQ is registered (visible in startup log as `Quantization: registered=SDNQ`)
but not activated. INT8 would give ~2× speed at unacceptable quality cost for
demanding composite prompts.

## Variational Auto Encoder 🔴

| Setting | Value | Mark |
|---|---|---|
| VAE model | **`sdxl_vae.safetensors`** | 🟡 explicit selection (not `Automatic`) — pins the SDXL stock VAE so hires / refine decisions are deterministic across model swaps |
| VAE upcasting | **`true`** | 🟢 **non-negotiable** — FP32 VAE prevents black patches in hires at strength 0.99 |
| Full precision (--no-half-vae) | `False` | ⚪ (upcast above handles it) |
| VAE slicing | **`True`** | 🟡 saves some VRAM |
| VAE tiling | **`True`** | 🔴 required for 1152×1632 decode on 16GB |
| VAE tile size | **`1024`** | 🔴 covers image width 1152 comfortably (1024 + overlap 128 = 1152); validated stable for hires 1152×1632 |
| VAE tile overlap | `0.125` | 🟡 halved from default 0.25 for speed; raise if seams appear |
| Remote VAE | off | ⚪ |

## Text Encoder

| Setting | Value | Mark |
|---|---|---|
| Text encoder model | `Default` | ⚪ |
| Prompt attention parser | **`a1111`** | 🟡 A1111-style weight syntax compatibility |
| Text encoder cache size | `16` | 🟡 cache prompt embeddings |
| Use line break as prompt segment marker | `True` | 🟡 enables `BREAK` semantics |
| Use zeros for prompt padding | `True` | 🟡 |
| T5 shared instance | `True` | ⚪ |
| SDXL weighted pooled embeds | `False` | ⚪ |

## Compute Settings 🔴

| Setting | Value | Mark |
|---|---|---|
| Device precision type | **`BF16`** | 🔴 A770 has no hardware BF16 conversion but FP16 causes NaN/black on composite prompts. BF16 is the stable choice — see `06-pipeline-tradeoffs.md` |
| Force full precision (--no-half) | `False` | 🟢 |
| Generator device | **`CPU`** | 🟡 cross-platform seed determinism |
| Attention method | **`Scaled-Dot-Product`** | 🟢 only viable XPU option |
| SDP kernels | **`Memory + Math`** | 🟢 Flash unavailable on XPU |
| SDP overrides | `None` | ⚪ |
| Attention slicing | **`Disabled`** | 🟡 VRAM is sufficient |
| xFormers options | **`None`** | 🟢 xformers has no XPU build |
| Dynamic Attention slicing rate | `0.5` | ⚪ (only if slicing enabled) |

## Backend Settings 🔴

| Setting | Value | Mark |
|---|---|---|
| Channels last | `False` | 🟢 NHWC layout incompatible with some XPU ops |
| Deterministic mode | `False` | ⚪ XPU has no cuDNN anyway |
| Fused projections | **`True`** | 🔴 ~1-3% speedup by fusing Q/K/V matmul |
| Expandable segments | **`True`** | 🔴 pairs with `max_split_size_mb:512` env var |
| cuDNN enabled | `default` | ⚪ (N/A on XPU) |
| cuDNN full-depth benchmark | `True` | ⚪ (N/A on XPU) |
| Tunable ops | `False` | ⚪ |
| Memory limit | `0` (unlimited) | ⚪ |
| GC threshold | **`80`** | 🟡 raised from default 70 → GC triggers a bit later, fewer interruptions |
| Inference mode | **`no-grad`** | 🟢 |
| Memory allocator | `native` | ⚪ |
| ONNX Execution Provider | `OpenVINOExecutionProvider` | ⚪ (not used in torch-xpu path) |
| ONNX options | defaults | ⚪ |
| Olive (ONNX optimization) | defaults | ⚪ |
| IPEX Optimize | `None` | ⚪ (intel_extension_for_pytorch package not installed; torch 2.11.0+xpu has XPU path built-in) |

## Pipeline Modifiers 🔴 (partial)

| Setting | Value | Mark |
|---|---|---|
| **CLiP Skip** | off | ⚪ |
| **Token Merging** — method | `None` | ⚪ (enable to use `ToMe` or `ToDo`) |
| ToMe token merging ratio | `0.3` (if enabled) | ⚪ |
| ToDo token merging ratio | `0.3` (if enabled) | ⚪ |
| **FreeU** — enabled | `False` (by default in this repo's config) | ⚪ |
| FreeU 1st/2nd stage backbone/skip | (values from config: 1.05 / 1.1 / 0.6 / 0.4) | ⚪ only applied if FreeU enabled |
| **PAG** layer names | `m0` | ⚪ |
| **PAB** (Pyramid attention broadcast) | `False` | ⚪ |
| **Cache-DiT** | `False` | ⚪ (SDXL is not DiT) |
| **Faster Cache** | `False` | ⚪ |
| **Para-attention** first-block cache | `False` | ⚪ |
| **TeaCache** enabled | **`True`** | 🟡 ~5% speedup, minimal quality impact |
| TeaCache L1 threshold | `0.10` | 🟡 (`0.15` for milder skipping) |
| **HyperTile** UNet enabled | **`False`** | 🟡 rejected in favor of `Fused projections`; HyperTile costs quality at tile boundaries |
| HyperTile HiRes pass only | `True` | ⚪ (if enabled) |
| HyperTile UNet tile size | `512` | ⚪ |
| HyperTile UNet min tile | `128` | ⚪ |
| HyperTile UNet swap size | `2` | ⚪ |
| HyperTile UNet depth | `2` | ⚪ |
| **HiDiffusion** RAU-Net / MSW-MSA | both `False` | 🟢 conflicts with custom SDXL merges |
| **LinFusion** | `False` | ⚪ |
| **RAS** (Region-Adaptive Sampling) | `False` | ⚪ |
| **CFG-Zero** | `False` | ⚪ |
| Batch sequential seeds | `True` | ⚪ |
| Parallel process images in batch | `False` | ⚪ |

## Model Compile

Not used. `torch.compile` on XPU is immature (as of 2026-04) and fails the C++
compilation path on Windows without MSVC in PATH.

| Setting | Value | Mark |
|---|---|---|
| Compile Model | **`None`** | 🟢 leave off |
| Model compile backend | `inductor` | ⚪ (only used if above is on) |
| Model compile mode | `default` | ⚪ |
| Model compile options | defaults | ⚪ |
| DeepCache cache interval | `3` | ⚪ |

## System Paths

Defaults are fine. These just define folder locations under `models\`:

- `models\Stable-diffusion`, `models\Diffusers`, `models\VAE`, `models\UNET`,
  `models\Lora`, `models\embeddings`, `models\styles`, `models\wildcards`,
  `models\yolo`, `models\control`, `models\ESRGAN`, `models\RealESRGAN`,
  `models\SCUNet`, `models\SwinIR`, etc.

## Image Options

| Setting | Value | Mark |
|---|---|---|
| Save all generated images | `True` | ⚪ |
| Save interrupted images | `False` | ⚪ |
| File format | `png` | 🟡 lossless; set to `webp` for smaller files |
| Image quality | `100` | ⚪ |
| Max image size (MP) | `2000` | ⚪ |
| WebP lossless compression | `True` | ⚪ |
| Include mask in outputs | `False` | ⚪ |
| Resize background color | `Black` | ⚪ |
| Grid Options | defaults | ⚪ |
| Watermarking | off | 🟢 |
| Intermediate image saving (before hires / refiner / detailer) | `False` | ⚪ |

## Image Paths

| Setting | Value | Mark |
|---|---|---|
| Numbered filenames | `True` | ⚪ |
| Save images to subdirectory | `True` | 🟡 |
| Directory pattern | `[date]-[model_name]` | 🟡 |
| Filename pattern | `[date]-[width]x[height]-[seq]-seed=[seed]` | 🟡 useful for long runs |

## Image Metadata

| Setting | Value | Mark |
|---|---|---|
| Include metadata in image | `False` | 🟡 some users prefer True for post-hoc reproducibility; False keeps PNGs clean for publishing |
| Save metadata to text file | `False` | ⚪ |
| Restore from metadata: skip settings | `sd_model_checkpoint + sd_vae + sd_unet + sd_text_encoder` | ⚪ |

## User Interface

| Setting | Value | Mark |
|---|---|---|
| Theme type | `Modern` | ⚪ |
| Theme mode | `Dark` | ⚪ |
| UI theme | `Default` | ⚪ |
| Autolaunch browser on startup | `False` | ⚪ (we use bat's delayed start instead) |
| UI request timeout | `120000` ms | ⚪ |
| UI locale | `en: English` | ⚪ |
| Compact view | `True` | 🟡 more settings visible per screen |

## Live Previews

| Setting | Value | Mark |
|---|---|---|
| Live preview display period | `0` | 🟡 disabling live preview saves ~5% |
| Progress update period | `5000` ms | ⚪ |

## Postprocessing

Where the face detailer (and upscaler globals) live.

| Setting | Value | Mark |
|---|---|---|
| Apply color correction | `False` | ⚪ |
| Apply mask as overlay | `False` | ⚪ |
| Inpainting conditioning mask strength | `0.5` | ⚪ |
| Move detailer model to CPU when complete | `False` | ⚪ |
| Detailer use model augment | `False` | ⚪ |
| Face restoration (CodeFormer / GFPGAN) | `None` | 🟢 legacy, use detailer instead |

### Detailer defaults (Settings → Postprocessing → Detailer)

These are the *global* detailer defaults that apply when the per-image control
panel isn't overriding them. Some were tuned to be less aggressive than
SD.Next's defaults based on production observation.

| Setting | Value | Default | Mark |
|---|---|---|---|
| Detailer confidence threshold | **`0.4`** | `0.6` | 🟡 lower = catches faces at more angles / smaller sizes; combine with `Max detected = 1` to avoid false positives |
| Max detected | **`1`** | `2` | 🟡 only the single main face |
| Detailer min size | **`0.05`** | `0.0` | 🟡 skips YOLO boxes under 5% of image area — rejects accidental background blobs |
| Detailer max size | `1.0` | `1.0` | ⚪ |
| Edge padding | **`48`** | `20` | 🟡 raised — gives the inpaint context room around the face crop, prevents hard boundary artifacts |
| Edge blur | **`20`** | `10` | 🟡 raised — softens the paste-back edge, avoids visible rectangle around the detailer region |
| Max overlap (IoU) | `0.5` | `0.5` | ⚪ |
| Detailer sigma adjust max | `0` | `1.0` | 🟡 disables sigma adjust ramp for detailer pass |

### Upscaler defaults

| Setting | Value | Mark |
|---|---|---|
| Unload upscaler after processing | `True` | 🟡 frees VRAM |
| Upscaler latent steps | `4` | ⚪ (only if using Latent upscaler; we use WAN) |
| Upscaler tile size | `640` | ⚪ |
| Upscaler tile overlap | `48` | 🟡 raised from default 8 to prevent ESRGAN seams |

## Huggingface

| Setting | Value | Mark |
|---|---|---|
| Use cached model config when available | `True` | ⚪ |
| Download method | `rust` | 🟡 faster than `request` |
| Force offline mode | `False` | ⚪ |
| Preferred model variant | `default` | ⚪ |

## Networks (LoRA / Embeddings / Styles / Wildcards)

| Setting | Value | Mark |
|---|---|---|
| Default strength | `1` | ⚪ |
| LoRA force reload always | `False` | 🟢 |
| LoRA load using Diffusers method | **`True`** | 🟡 |
| LoRA native apply to text encoder | `False` | ⚪ |
| **LoRA native fuse with model** | **`True`** | 🔴 **critical for long-run stability** — fuses LoRA into UNet on load, avoids per-step merge/unmerge cycle that fragments XPU memory |
| LoRA diffusers fuse with model | `False` | 🟢 don't enable both fuse types |
| LoRA auto-apply tags | `0` | ⚪ |
| LoRA memory cache | `1` | 🟡 keep only active LoRA (reduce from default 10 if not hot-swapping) |
| LoRA add hash info to metadata | `True` | 🟡 useful for reproducing which LoRA was used |
| Embeddings support | `True` | ⚪ |
| Auto-convert SD1.5 embeddings to SDXL | `False` | ⚪ |
| File wildcards support | `True` | ⚪ |
| Enable use of reference models | `True` | ⚪ |

## Extensions

| Setting | Value | Mark |
|---|---|---|
| Disable all extensions | `None` | ⚪ |

Our built-in extensions stay enabled: `sd-extension-chainner`,
`sd-extension-system-info`, `sdnext-kanvas`, `sdnext-modernui`.

---

## Minimal critical changes from SD.Next default

If you only apply the 🔴-marked settings, you get the core stability and
performance benefits documented in this repo:

1. `Model offload mode: none`
2. `Modules to always offload: ""` (empty)
3. `VAE upcasting: true`
4. `VAE tiling: true` + `tile size: 1088`
5. `Device precision type: BF16`
6. `SDP kernels: Memory + Math`
7. `Fused projections: true`
8. `Expandable segments: true`
9. `Compile Model: None` (don't enable it)
10. `LoRA native fuse with model: true`

The 🟡 settings add incremental gains on top. The rest are defaults that
SD.Next chose well.
