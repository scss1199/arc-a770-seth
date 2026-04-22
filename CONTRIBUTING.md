# Contributing

Thanks for your interest. This repo is a living document — the A770 + SD.Next
stack evolves and findings here will go stale without community help.

## What's most useful

1. **Validation on other Arc GPU variants** — A750, A580, A380, B580, B570.
   If you can reproduce the stability results (0 OOM in 8+ hr run) with a
   different card, open a PR adding notes to `docs/04-a770-hardware-notes.md`.

2. **Newer driver / oneAPI / torch-XPU versions** — when you update, run a
   short benchmark and comment on what changed. Post results in an Issue.

3. **Different CPUs** — CPU affinity mask table in `docs/02-env-vars.md` is
   based on Raptor Lake / Raptor Lake Refresh. Other hybrid CPUs (Meteor Lake,
   Arrow Lake, upcoming Nova Lake) will need different masks.

4. **Alternative launch scripts** — PowerShell, WSL bash equivalents, or a
   Python launcher. Keep them in `launch/` with distinct names.

5. **Regressions** — if a configuration that previously worked no longer does
   on a new stack, open an Issue with before/after log excerpts.

## Style guide

- **Documentation in bilingual** (English + 中文) where practical.
- **Rationale must be specific.** "This is faster" is not useful; "this is
  ~8 s faster per hires VAE decode on A770 1152×1632" is.
- **Show your work.** Include log excerpts, `torch.xpu.get_device_properties`
  output, benchmark commands. Others need to reproduce.
- **Timestamp discoveries.** Driver versions, package versions, and Windows
  build numbers change fast. Date your findings.

## Commit message style

Prefix commits with scope, e.g.:
```
docs(env-vars): explain REUSE_DISCARDED_EVENTS
launch: add affinity mask for i9-14700K
bench: A750 8GB sustained 12hr run results
```

## PR checklist

- [ ] Tested on actual hardware (not just documented)
- [ ] Includes version info (torch, oneAPI, SD.Next commit, driver)
- [ ] Rationale explained, not just "change X"
- [ ] If adding a new doc, linked from README
- [ ] No personal prompts, model names, or output images

## Reporting issues

Include at minimum:
- Hardware (GPU model, driver version, CPU, RAM)
- OS version (Windows build or Linux distro)
- `torch` version, `intel-sycl-rt` version, SD.Next commit
- Short log excerpt from `sdnext.log` (sanitize prompts)
- What you expected vs what happened
