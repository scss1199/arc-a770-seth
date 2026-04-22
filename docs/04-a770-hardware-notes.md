# 04 — Arc A770 hardware notes

These observations about the A770 matter for tuning decisions. All of them come
from `torch.xpu.get_device_properties(0)` run under torch 2.11.0+xpu or from
experience in long continuous runs.

## Hardware capability table (as reported by torch.xpu)

```
Intel(R) Arc(TM) A770 Graphics
  gpu_eu_count:                                  512     # 32 Xe-cores × 16 EU
  max_compute_units:                             512
  local_mem_size:                                65536   # 64 KB shared mem per work-group
  max_work_group_size:                           1024
  sub_group_sizes:                               [8, 16, 32]
  total_memory:                                  16704737280  # 16 GB
  has_fp16:                                      True
  has_fp64:                                      False   # no FP64
  has_atomic64:                                  True
  has_bfloat16_conversions:                      False   # ⚠️ critical
  has_subgroup_matrix_multiply_accumulate:       False   # ⚠️ no XMX subgroup MMA
  has_subgroup_matrix_multiply_accumulate_tensor_float32:  False
  has_subgroup_2d_block_io:                      False
  driver_version:                                1.13.35227
  platform_name:                                 Intel(R) oneAPI Unified Runtime over Level-Zero
```

## The three most important findings

### 1. `has_bfloat16_conversions: False` — BF16 is software-emulated

**A770 silicon has NO hardware path for BF16 conversion.** When you run
`torch.bfloat16` tensors, arithmetic happens via software fallback or FP32
emulation with BF16 tensor packaging. This is the **single biggest untapped
performance opportunity on this platform**.

Implications:
- Current BF16 pipeline is not using Arc's peak theoretical throughput
- FP16 *would* use the hardware path (`has_fp16: True`) — potentially 20–40% faster
- But this repo sticks with BF16 because FP16 causes NaN / black images in SDXL
  merge checkpoints tested. See `06-pipeline-tradeoffs.md` for the full argument.

### 2. `has_subgroup_matrix_multiply_accumulate: False` — no XMX subgroup MMA

A770 has XMX ("Xe Matrix eXtensions") hardware for INT8 matrix multiply, but
torch.xpu reports **no subgroup-level MMA** for FP16/BF16 tensor ops.

Implications:
- SDXL matmul paths cannot benefit from XMX through the normal subgroup intrinsics
- Intel's library layer (oneDNN, MKL) may route through XMX for INT8 specifically
  but current stack does not quantize to INT8 (SDNQ registered but not enabled)
- INT8 quantization via SDNQ *would* unlock XMX for ~2× compute speedup, at
  unacceptable quality cost for realistic photo workflows

### 3. `has_subgroup_2d_block_io: False` — breaks several Triton kernels

Triton's efficient 2D tiled load/store patterns (used in flash-attention-like
kernels) require this hardware feature. Without it:
- Many community Triton kernels fall back to less optimal code paths
- SD.Next's Triton test compiles (with correct encoding setup) but the kernels
  produced are no faster than SDPA's Memory + Math fallback

See `07-troubleshooting.md` for the Triton test failure details.

## Memory subsystem

- **16 GB GDDR6** — sufficient for SDXL base 768×1088 + hires 1.5× + detailer 1024
  with the configuration in this repo. Typical peak observed: **11.24 GB**.
- **~560 GB/s** memory bandwidth — higher than RTX 4060's 272 GB/s, lower than
  RTX 4060 Ti 16GB's 288 GB/s. VAE decode is memory-bound and benefits from this.
- **64 KB local memory per work-group** — limits certain tiled kernel strategies.

## Two XPU devices reported

```python
>>> torch.xpu.device_count()
2
```

On Windows, torch.xpu reports two devices. In practice only one is the physical
A770; the other is typically a render-proxy. Setting `ZE_AFFINITY_MASK=0` and
`ONEAPI_DEVICE_SELECTOR=level_zero:0` pins to the physical device.

## Driver version matters

Intel Arc drivers update frequently with compute-path fixes. Version in this
repo is `1.13.35227`. Each driver release can fix or introduce long-run bugs.
**Test a new driver on a short run before committing it to an 8-hour job.**

Check driver version via:
```powershell
Get-WmiObject Win32_VideoController |
  Where-Object { $_.Name -match "Arc" } |
  Select-Object Name, DriverVersion
```

## Triton XPU (3.7.0 installed, limited usefulness)

The package `triton-xpu` is bundled with `torch 2.11.0+xpu`. It can import and
accept `@triton.jit` kernels. However:
- SD.Next's `torch.compile(fullgraph=True)` test fails because Torch Inductor's
  C++ compilation pass cannot find a compatible compiler under Windows
- Even if the test passes, the kernels Inductor generates for SDXL's matmul
  hotpaths are generally **not faster** than SDPA's native fallback because
  of the missing hardware features above

This is why `triton=fail` in SD.Next's parameter log is **expected and harmless**
for this configuration.

## Community benchmarks for reference

| GPU | Theoretical FP16 TFLOPS | SDXL 1024×1024 base sampling (IPEX/XPU) |
|---|---|---|
| RTX 4060 (8 GB) | 15 | ~7 it/s (CUDA) |
| RTX 4060 Ti 16GB | 22 | ~8 it/s (CUDA) |
| **Arc A770 16GB** | **20** | **~1.5–2.0 it/s (XPU)** |
| Arc B580 12GB | ~28 | ~3–4 it/s (XPU, Battlemage XMX improved) |

The gap between A770's theoretical 20 TFLOPS and its observed ~2 it/s is
mostly the software stack — torch-XPU + IPEX path is less mature than CUDA +
TensorRT. The underlying silicon is capable; the glue is thin.
