# SD.Next tuning for Intel Arc A770

A production-tested configuration for running [SD.Next](https://github.com/vladmandic/sdnext)
on **Intel Arc A770 (16GB)** under Windows 11, optimized for **long-run stability** of
SDXL pipelines (hires + detailer, 10+ hour continuous generation, zero OOM, zero retries).

This repo distills one year of empirical tuning into a reproducible setup: environment
variables, SYCL/Level Zero runtime flags, SD.Next internal settings, and startup script.

## Why this repo exists

The Arc A770 community for AI image generation is small and documentation is scattered.
Most guides target NVIDIA. Many Arc-specific settings that matter — e.g. which `SYCL_PI_*`
flags to disable to avoid long-run cache corruption — are tribal knowledge only findable
by reading Intel-LLVM DLL strings or burning hours on failed runs.

This setup has been validated with:

- **8+ hour continuous long-run** at ~106s/image (SDXL 768×1088 → hires 1.5x → face detailer)
- **Zero OOM, zero retries** across 270+ sequential images with random seeds
- **11.24 GB peak VRAM** (stable, no drift)
- Base sampling 2.67 it/s · Hires sampling 1.37 it/s — at or above community A770 benchmarks

## Tested stack

| Component | Version |
|---|---|
| GPU | Intel Arc A770 16GB |
| Driver | 1.13.35227 |
| CPU | Intel Core i9-14900K (13900K die, hybrid P/E cores) |
| Windows | 11 (10.0.26200+) |
| SD.Next | commit `0eb4a98e0` (2026-04-04) |
| torch | 2.11.0+xpu |
| intel-sycl-rt | 2025.3.2 (via pip, bundled in venv) |
| oneAPI | 2025.3 (venv) / 2025.2 (system) |
| Python | 3.12.10 |

## Quick start

1. Install SD.Next per upstream instructions. Verify it runs once with their default launch.
2. Copy [`launch/sd_next_a770.bat`](launch/sd_next_a770.bat) to your SD.Next root.
3. Edit the path variables at the top of the bat to match your install.
4. Run the bat. If it crashes, run it from an already-open `cmd` so you can see the error.

Detailed rationale for every setting lives in [`docs/`](docs/):

- [01 — Quick start](docs/01-quick-start.md)
- [02 — Environment variables explained](docs/02-env-vars.md)
- [03 — SD.Next UI settings (high-priority)](docs/03-sdnext-settings.md)
- [04 — A770 hardware notes](docs/04-a770-hardware-notes.md)
- [05 — Benchmarks](docs/05-benchmarks.md)
- [06 — Pipeline tradeoffs (FP16 vs BF16, VAE upcast, etc.)](docs/06-pipeline-tradeoffs.md)
- [07 — Troubleshooting (issues encountered in the wild)](docs/07-troubleshooting.md)
- [08 — Detailer / Refiner decoupling patch](docs/08-detailer-refiner-fix.md)
- [10 — SD.Next UI full parameter reference (exhaustive, per-page)](docs/10-sdnext-ui-full-reference.md)
- [11 — Multi-stage prompt framework (six-block architecture)](docs/11-prompt-framework.md)

## Patches

The `patches/` directory contains small, reviewed fixes to SD.Next that were
discovered during long-run tuning on A770 and are not yet merged upstream.
Each patch is a git-format unified diff with a full context header. Apply
them against your SD.Next install with:

```bash
python tools/apply_patches.py --dry-run     # preview
python tools/apply_patches.py               # apply with .orig backup
python tools/apply_patches.py --revert      # restore backups
```

Current patches:

| Patch | Target | Summary |
|---|---|---|
| `detailer-refiner-decouple.patch` | `modules/processing_diffusers.py` | Makes `Detailer strength` actually work by stopping it from inheriting `Refiner start`. See [doc 08](docs/08-detailer-refiner-fix.md). |

## Key findings in one page

- **A770 has NO hardware BF16 conversion** (`has_bfloat16_conversions: False` via torch.xpu).
  BF16 operations go through a software/FP32 path. FP16 *would* be faster but triggers
  NaN / black-image issues in SDXL merge checkpoints under the current stack. BF16 is a
  deliberate stability-over-speed tradeoff — not an oversight.
- **VAE must run FP32 upcast** for SDXL hires img2img at strength 0.99 or the refine pass
  produces black patches from BF16 NaN propagation. Non-negotiable.
- **Intel caches should all be disabled** (`IGC_EnableShaderCache=0`, `IPEX_WEIGHT_CACHE=0`,
  `SYCL_CACHE_PERSISTENT=0`, `IPEX_XPU_ONEDNN_LAYOUT=OFF`). Cache corruption causes
  wrong-output / OOM / crash in long run three different ways; clean-after-crash workflow
  was worse than never caching.
- **SYCL_PI_LEVEL_ZERO_*** env vars are **not deprecated** on the v1 L0 adapter despite
  the UR (Unified Runtime) migration. Verified by scanning `ur_adapter_level_zero.dll`
  string tables — all 446 env vars the adapter reads still use the `SYCL_PI_*` prefix.
- **`max_split_size_mb:512`** on `PYTORCH_XPU_ALLOC_CONF` is the sweet spot for hires VAE
  decode on 16 GB. 256 too tight (hires fragmentation), 1024 risks underutilization.
- **P-core affinity + HIGH priority** matters on 14900K / 13900K hybrid CPUs for
  CPU-bound pipeline stages (YOLO face detection, prompt parsing, VAE resize).
  Windows scheduler will occasionally park Python on E-cores without explicit affinity.

## What this repo does NOT contain

- Model recommendations (use whichever SDXL checkpoint you like)
- Specific prompt examples (out of scope; personal taste) — **but** doc 11
  documents the multi-stage prompt *architecture* (template / structure / rules)
  agnostic to content
- LoRA / embedding files
- Output images

## Contributing

PRs welcome. Especially:
- Other Arc GPU variants (A750, A580, B580) if you've validated the same settings
- Bug reports on this config with other Windows versions / driver versions
- Alternative startup scripts (PowerShell, bash via WSL)

## License

MIT — see [LICENSE](LICENSE).

## Credits

Maintained by **Seth Chou** ([@scss1199](https://github.com/scss1199)) —
formerly Intel HW Platform Debug and ARC HW team (Taiwan).
Computex 2023 A770 demos background.

Tuning was collaboratively refined across a long session with an AI assistant
(Anthropic Claude), but every setting was validated against live production runs
on the author's hardware.

---

# 中文說明

這份 repo 收錄一年摸索 Intel Arc A770 跑 SD.Next 的穩定生產配置 — 環境變數、SYCL/Level Zero runtime 設定、SD.Next 內部參數、啟動腳本，全部都是實際驗證過的。

針對需求：**SDXL pipeline（base + hires + detailer）長時間連續生成、不崩、不 OOM**。

### 為什麼開這個 repo

A770 跑 AI 繪圖社群小、文件散，大部分指南都以 NVIDIA 為主。Arc 特有的關鍵設定（例如哪些 `SYCL_PI_*` 必須關閉以避免 long run cache 損毀）是踩雷才知道的隱性知識，這份設定試圖把它們一次整理清楚。

### 驗證結果

- **8 小時以上連續生成**，每張約 106 秒（768×1088 → hires 1.5x → face detailer）
- **270+ 張不同 seed，0 OOM / 0 retries**
- **Peak VRAM 11.24 GB 穩定不漂移**
- Base sampling 2.67 it/s · Hires 1.37 it/s — 達到或超過 A770 社群基準

### 快速起步

1. 按 SD.Next 官方指引裝好，先確認能用原本的啟動方式跑一張
2. 複製 [`launch/sd_next_a770.bat`](launch/sd_next_a770.bat) 到 SD.Next 根目錄
3. 編輯 bat 檔頭的路徑變數對應你的安裝位置
4. 執行。若閃退，從已開的 cmd 視窗手動跑以便看錯誤訊息

詳細說明在 [`docs/`](docs/)，每個決定都附理由。

### Patches（SD.Next 補丁）

`patches/` 目錄收錄 A770 長跑中發現、尚未進上游的 SD.Next 小修補。每個都是完整
git-format patch 附 context header。用法：

```bash
python tools/apply_patches.py --dry-run     # 預覽
python tools/apply_patches.py               # 套用（自動 .orig 備份）
python tools/apply_patches.py --revert      # 還原
```

目前的補丁：

- `detailer-refiner-decouple.patch` — 修好 `Detailer strength` 這個長期失靈的
  參數，原因是它意外繼承了 `Refiner start` 的 denoising schedule。詳見
  [doc 08](docs/08-detailer-refiner-fix.md)。

### 不在本 repo 範圍的

- 模型推薦（自選）
- Prompt 範例（個人品味）
- LoRA / embedding 檔案
- 產出圖片

### 授權

MIT — 歡迎 fork、改造、送 PR。
