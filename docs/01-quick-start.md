# 01 — Quick start

## Prerequisites

1. **SD.Next installed and working** at `C:\sd_next_a770\` (or wherever you choose).
   Verify it launches and generates one image under its own default settings first.
2. **Intel oneAPI toolkit installed** — default path is
   `C:\Program Files (x86)\Intel\oneAPI\`.
3. **Intel Arc driver up to date** (this repo tested with `1.13.35227`).
4. **Windows 11** (10.x builds may also work but untested).

## Steps

1. **Copy the launch script.** Copy
   [`launch/sd_next_a770.bat`](../launch/sd_next_a770.bat) into your SD.Next root folder.
2. **Edit the USER CONFIGURATION block at the top.** There are four lines to customize:

   ```batch
   set "SDNEXT_ROOT=C:\sd_next_a770"
   set "ONEAPI_SETVARS=C:\Program Files (x86)\Intel\oneAPI\setvars.bat"
   set "EDGE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
   set "CPU_AFFINITY=FFFF"
   ```

   - `SDNEXT_ROOT` — your SD.Next installation folder.
   - `ONEAPI_SETVARS` — path to Intel oneAPI's `setvars.bat`.
   - `EDGE_PATH` — browser auto-launcher (optional; set to `""` to skip).
   - `CPU_AFFINITY` — hex mask for CPU cores. See table in the bat header.
3. **Run the bat.** Double-click, or from an open `cmd`:
   ```
   cd C:\sd_next_a770
   sd_next_a770.bat
   ```
   The first time, run it from an **already-open `cmd` window** so the window does
   not close on error.

4. **Verify in log.** SD.Next's startup log should show:

   - `Args: ['--use-ipex', '--backend', 'diffusers', ...]` — single occurrence, no duplicates
   - `Torch parameters: backend=ipex device=xpu config=BF16 ...`
   - `Device: device=Intel(R) Arc(TM) A770 Graphics ...`
   - `fp16=pass bf16=pass triton=fail` — `triton=fail` is expected and harmless
     (XPU Triton path is not yet viable; see `07-troubleshooting.md`)

5. **Verify in Task Manager.** While SD.Next is running:
   - Right-click `python.exe` → Set priority should show **High**.
   - Right-click `python.exe` → Set affinity should only have CPU 0-15 checked
     (P-cores on 14900K / 13900K).

## First image

Generate a 768×1088 SDXL image with your preferred checkpoint. A rough baseline
for this repo's configuration is:

| Stage | Expected time |
|---|---|
| Base sampling (16 steps) | ~6 s |
| VAE decode + upscale | ~3–5 s (depends on upscaler) |
| Hires sampling (12–20 steps at 1152×1632) | ~15–20 s |
| Face detailer | ~10–15 s (first image includes YOLO model load) |
| Total (first image) | ~60–90 s |
| Total (steady state, from image #2 onward) | ~100–110 s |

If your numbers are dramatically worse (2× slower or more), check
[`07-troubleshooting.md`](07-troubleshooting.md).

## Safe rollback

The bat auto-backs up `config.json` and `ui-config.json` to `*_backup.json` on
every startup (if they are > 1 KB — small-file guard against backing up a
corrupted config over the old good one).

If anything breaks:

```batch
copy /y config_backup.json config.json
copy /y ui-config_backup.json ui-config.json
```
