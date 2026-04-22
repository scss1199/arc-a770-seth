# 02 — Environment variables explained

Every environment variable in [`launch/sd_next_a770.bat`](../launch/sd_next_a770.bat)
with its rationale. Values shown are the defaults set by the launch script.

## Python encoding — fixes Triton test encoding errors

```batch
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

Without these, on CJK (Traditional Chinese / Japanese) Windows locales, SD.Next's
Triton test can fail with `UnicodeDecodeError: 'cp950' codec can't decode byte ...`
during `torch.compile`'s C++ compilation pass, which also **adds ~20 s of wasted
timeout to startup**. Setting Python to UTF-8 mode resolves it. The Triton test
will still fail afterward on XPU (for different reasons — see `07-troubleshooting.md`)
but at least it fails quickly instead of burning 20 s.

## Intel GPU device selection

```batch
set ONEAPI_DEVICE_SELECTOR=level_zero:0
set ZE_AFFINITY_MASK=0
```

Binds to the first Level Zero device (the Arc A770). `torch.xpu.device_count()`
on A770 systems reports **2 devices** (one physical GPU + one render proxy) —
both variables ensure we pick the first.

## All Intel GPU caches — disabled

```batch
set IGC_EnableShaderCache=0
set IPEX_WEIGHT_CACHE=0
set IPEX_XPU_ONEDNN_LAYOUT=OFF
set SYCL_CACHE_PERSISTENT=0
```

### Why disabled

On long continuous runs (8+ hours of SDXL generation), these caches have been
observed to corrupt in **three different failure modes**:

1. **Wrong output** — silently produce black patches or color-shifted regions
2. **OOM** — cache directory grows unbounded, driver runs out of backing store
3. **Crash** — stale cache entries fail to load, Python process terminates

Manual cache-clean-after-crash workflows were **worse** than never caching —
because detection of the corruption requires visual inspection and by the time
you notice, the last hour of images is all wasted.

### The cost

First-time kernel compilation per session (~10–30 s over startup). Negligible
compared to the variance that corruption introduces. Within a session, kernels
stay compiled in-process.

## Level Zero (v1 adapter) tuning

```batch
set SYCL_PI_LEVEL_ZERO_BATCH_SIZE=32
set SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0
set SYCL_PI_LEVEL_ZERO_DEVICE_SCOPE_EVENTS=0
set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1
set SYCL_PI_LEVEL_ZERO_REUSE_DISCARDED_EVENTS=1
```

### On the `SYCL_PI_*` prefix (not deprecated)

Starting oneAPI 2024+, the SYCL PI plugin system migrated to the Unified Runtime
(UR). Some guides claim `SYCL_PI_*` is deprecated and should be replaced with
`UR_L0_*`.

**This is incorrect for the default v1 adapter.** Direct inspection of the
string table inside `venv\Library\bin\ur_adapter_level_zero.dll` (oneAPI 2025.3)
shows all 446 environment variables the adapter reads still use the
`SYCL_PI_LEVEL_ZERO_*` prefix. The `UR_L0_*` names only appear in the v2
adapter (`ur_adapter_level_zero_v2.dll`), which is not enabled by default and
is **not recommended for production** as of 2026-04 — its `callback` timer is
2× slower than v1 on the same workload.

### Per-variable rationale

- **`BATCH_SIZE=32`** — batches 32 commands to the L0 driver per submission
  (reduces kernel launch overhead for the many small UNet kernels).
- **`USE_COPY_ENGINE=0`** — disables use of Arc's dedicated copy engine.
  Found empirically to avoid a long-run bug where D2H transfers would stall
  indefinitely. Trade-off: slightly slower VAE decode (copies run on compute
  engine instead).
- **`DEVICE_SCOPE_EVENTS=0`** — uses host-scope events instead of device-scope.
  Simpler sync semantics; another long-run stability choice.
- **`USE_IMMEDIATE_COMMANDLISTS=1`** — recommended by Intel for Arc's compute
  pattern. Reduces command list allocation overhead.
- **`REUSE_DISCARDED_EVENTS=1`** — pools discarded event objects rather than
  freeing/reallocating. Reduces host-side allocator pressure over long runs.
  Pure memory management optimization — does not change compute behavior.

## PyTorch XPU allocator

```batch
set PYTORCH_XPU_ALLOC_CONF=max_split_size_mb:512
```

The PyTorch XPU allocator splits memory into segments of at most this size before
handing to the caller. For SDXL hires at 1152×1632 with VAE decode fallback:

| Value | Outcome |
|---|---|
| 128 | Frequent hires OOM |
| 256 | OOM under memory pressure (LoRA + ControlNet) |
| **512** | **Stable — no OOM observed in 8+ hr run** |
| 1024 | Increased fragmentation waste; no perf benefit |

`torch_expandable_segments: true` is set in SD.Next's config (not here) and
works with `max_split_size_mb` to permit segment growth on demand.

## CPU affinity and priority

```batch
start "SD.Next" /B /WAIT /HIGH /AFFINITY FFFF python launch.py
```

- **`/B`** — keep output in the current console (no new window).
- **`/WAIT`** — the bat waits for Python to exit before hitting `exit /b`.
- **`/HIGH`** — Windows process priority. Above Normal, below Realtime.
  Do **not** use `/REALTIME` — it will starve the OS (keyboard / mouse freeze).
- **`/AFFINITY FFFF`** — binds Python to logical cores 0–15.
  On 14900K / 13900K, these are the 8 P-core threads (with HT).

### Why affinity matters on hybrid CPUs

Windows' scheduler occasionally parks Python on E-cores. Measured impact on
CPU-bound pipeline stages (YOLO face detection, prompt tokenization, VAE
pre/post resize): **0.3–1 s per image** over an 8-hour run this adds up.

Without affinity, tasks run on whichever cores the scheduler picks, which often
includes E-cores during mixed workloads.

### CPU affinity reference table

| CPU | Logical threads | P-core mask |
|---|---|---|
| i9-14900K / 13900K / 13900KF | 32 (8P×HT + 16E) | `FFFF` |
| i7-14700K / 13700K | 24 (8P×HT + 8E) | `FFFF` |
| i5-14600K / 13600K | 20 (6P×HT + 8E) | `FFF` |
| i5-14500 / 13500 | 20 (6P×HT + 8E) | `FFF` |
| All cores (no hybrid) | — | `FFFFFFFF` |

Verify the count on your system:
```batch
wmic cpu get NumberOfCores,NumberOfLogicalProcessors
```

## What is NOT set, and why

- **`IPEX_OPTIMIZE`** — ignored here because `intel_extension_for_pytorch` pip
  package is not installed. Modern `torch 2.11.0+xpu` includes the XPU backend
  natively, and SD.Next's `--use-ipex` flag just enables the XPU path.
- **`SYCL_UR_USE_LEVEL_ZERO_V2=1`** — tested, not adopted. v2 adapter is faster
  at VAE decode (~2.5 s saved) but has a callback path that is ~2× slower,
  net worse for this workload. Kept with v1.
- **`UR_L0_*`** — only relevant if v2 adapter is enabled; see above.
- **`/REALTIME` priority** — unsafe, can freeze OS.
- **Shader cache paths** — disabled via `IGC_EnableShaderCache=0` rather than
  redirecting, so there is no need to set cache location variables.
