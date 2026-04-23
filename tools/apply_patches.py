"""
Apply patches in `patches/` to your SD.Next install.

Creates a .orig backup of each touched file before applying, verifies the
SD.Next install is a git repo, and uses `git apply` for reliable application.

Usage (run from the root of this repo):

    python tools/apply_patches.py                       # apply all patches
    python tools/apply_patches.py --list                # list available patches
    python tools/apply_patches.py --dry-run             # check, don't apply
    python tools/apply_patches.py --revert              # restore .orig backups
    python tools/apply_patches.py --patch detailer-refiner-decouple.patch

    # Point at a custom SD.Next install:
    python tools/apply_patches.py --sdnext "D:\\sdnext"

Each patch file in `patches/` must be a git-format unified diff. Header
metadata (From, Subject, Target, File) above the `diff --git` line is
informational only; `git apply` ignores it.

The tool is idempotent per-patch: re-applying a patch that is already in
the tree is a no-op (git apply --check will refuse cleanly). Use --revert
to roll back.

Exit codes:
  0 = success (or nothing to do)
  1 = user error (bad paths, missing git)
  2 = patch failed to apply
"""
from __future__ import annotations
import argparse, pathlib, shutil, subprocess, sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PATCHES_DIR = REPO_ROOT / "patches"


def run(cmd: list[str], cwd: pathlib.Path, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=check, capture_output=True, text=True)


def verify_git_repo(path: pathlib.Path) -> bool:
    if not path.exists():
        print(f"ERROR: SD.Next path does not exist: {path}", file=sys.stderr)
        return False
    r = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    if r.returncode != 0 or r.stdout.strip() != "true":
        print(f"ERROR: not a git repo: {path}", file=sys.stderr)
        print("       SD.Next must be installed via `git clone` for patches to apply cleanly.", file=sys.stderr)
        return False
    return True


def extract_target_files(patch_path: pathlib.Path) -> list[str]:
    """Parse a git-format patch to extract the list of target file paths (b/...)."""
    targets = []
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            targets.append(line[6:].strip())
    return targets


def backup_file(sdnext: pathlib.Path, relpath: str) -> pathlib.Path | None:
    """Copy sdnext/relpath to sdnext/relpath.orig if not already backed up.
    Returns the backup path, or None if source missing."""
    src = sdnext / relpath
    if not src.exists():
        print(f"  WARN: target file missing, skip backup: {relpath}", file=sys.stderr)
        return None
    dst = src.with_suffix(src.suffix + ".orig")
    if dst.exists():
        print(f"  backup already exists: {dst.name}")
        return dst
    shutil.copy2(src, dst)
    print(f"  backup: {src.name} -> {dst.name}")
    return dst


def restore_file(sdnext: pathlib.Path, relpath: str) -> bool:
    src_orig = sdnext / (relpath + ".orig")
    if not src_orig.exists():
        print(f"  WARN: no backup to restore: {relpath}.orig", file=sys.stderr)
        return False
    dst = sdnext / relpath
    shutil.copy2(src_orig, dst)
    print(f"  restored: {relpath} from .orig")
    return True


def list_patches() -> list[pathlib.Path]:
    if not PATCHES_DIR.exists():
        return []
    return sorted(PATCHES_DIR.glob("*.patch"))


def apply_one(patch_path: pathlib.Path, sdnext: pathlib.Path, dry_run: bool) -> bool:
    print(f"\n=== {patch_path.name} ===")
    targets = extract_target_files(patch_path)
    if not targets:
        print(f"  ERROR: no target files found in patch", file=sys.stderr)
        return False
    for t in targets:
        print(f"  target: {t}")

    # Check applicability
    check = run(["git", "apply", "--check", str(patch_path)], cwd=sdnext)
    if check.returncode != 0:
        # Check if already applied by attempting reverse
        rev_check = run(["git", "apply", "--check", "--reverse", str(patch_path)], cwd=sdnext)
        if rev_check.returncode == 0:
            print(f"  already applied (reverse check passed) - skip")
            return True
        print(f"  ERROR: patch does not apply cleanly:", file=sys.stderr)
        print(check.stderr, file=sys.stderr)
        return False

    if dry_run:
        print(f"  [dry-run] would apply cleanly")
        return True

    # Backup before applying
    for t in targets:
        backup_file(sdnext, t)

    # Apply
    apply_res = run(["git", "apply", str(patch_path)], cwd=sdnext)
    if apply_res.returncode != 0:
        print(f"  ERROR: git apply failed:", file=sys.stderr)
        print(apply_res.stderr, file=sys.stderr)
        return False
    print(f"  applied")
    return True


def revert_all(patches: list[pathlib.Path], sdnext: pathlib.Path) -> int:
    rc = 0
    for p in patches:
        print(f"\n=== revert {p.name} ===")
        targets = extract_target_files(p)
        for t in targets:
            if not restore_file(sdnext, t):
                rc = 2
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sdnext", default=r"C:\sd_next_a770",
                    help="Path to your SD.Next install (must be a git repo)")
    ap.add_argument("--list", action="store_true", help="list available patches and exit")
    ap.add_argument("--patch", help="apply only this patch by filename (e.g. detailer-refiner-decouple.patch)")
    ap.add_argument("--dry-run", action="store_true", help="check applicability, do not modify files")
    ap.add_argument("--revert", action="store_true", help="restore .orig backups for all target files")
    args = ap.parse_args()

    patches = list_patches()
    if args.list:
        if not patches:
            print("no patches found in patches/")
            return 0
        print(f"available patches ({len(patches)}):")
        for p in patches:
            targets = extract_target_files(p)
            print(f"  {p.name}  ->  {', '.join(targets) if targets else '(no targets found)'}")
        return 0

    if not patches:
        print("no patches found in patches/ — nothing to do")
        return 0

    if args.patch:
        patches = [p for p in patches if p.name == args.patch]
        if not patches:
            print(f"ERROR: patch not found: {args.patch}", file=sys.stderr)
            return 1

    sdnext = pathlib.Path(args.sdnext)
    if not verify_git_repo(sdnext):
        return 1

    if args.revert:
        return revert_all(patches, sdnext)

    failed = 0
    for p in patches:
        if not apply_one(p, sdnext, args.dry_run):
            failed += 1

    print()
    if failed:
        print(f"FAILED: {failed}/{len(patches)} patches did not apply", file=sys.stderr)
        return 2
    action = "would apply" if args.dry_run else "applied"
    print(f"OK: {action} {len(patches)}/{len(patches)} patches")
    if not args.dry_run:
        print("Restart SD.Next for changes to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
