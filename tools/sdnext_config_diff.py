"""
Compare your SD.Next config.json against the defaults declared in
SD.Next's ui_definitions.py. Lists every setting you have changed from
default, grouped by section.

Usage (run from inside SD.Next's venv):

    python tools/sdnext_config_diff.py
    python tools/sdnext_config_diff.py --all             # include unchanged keys
    python tools/sdnext_config_diff.py --orphans         # keys in config.json not in source (deprecated)
    python tools/sdnext_config_diff.py --section offload # only one section

    # Point at a custom install location:
    python tools/sdnext_config_diff.py \\
        --ui-def "D:\\sdnext\\modules\\ui_definitions.py" \\
        --config "D:\\sdnext\\config.json"

This is a read-only audit tool — it never writes to config.json.
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

SECTION_RE = re.compile(r"options_section\(\s*\(\s*['\"]([\w\-]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
OPTION_RE = re.compile(r'^\s*["\'](\w+)["\']:\s*OptionInfo\((.*)$')


def extract_first_arg(rest: str) -> str:
    depth = 0
    for i, c in enumerate(rest):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return rest[:i].strip()
            depth -= 1
        elif c == "," and depth == 0:
            return rest[:i].strip()
    return rest.strip()


def parse_default(s: str):
    s = s.strip()
    if s in ("True", "False", "None"):
        return {"True": True, "False": False, "None": None}[s]
    if s == "[]":
        return []
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return "<dynamic>"


def scan_ui_definitions(ui_def_path: pathlib.Path):
    lines = ui_def_path.read_text(encoding="utf-8").splitlines()
    defaults = {}
    section = None
    for i, line in enumerate(lines, start=1):
        m = SECTION_RE.search(line)
        if m:
            section = m.group(1)
            continue
        m = OPTION_RE.match(line)
        if m and section:
            key = m.group(1)
            if key.endswith("_sep"):
                continue
            default_raw = extract_first_arg(m.group(2))
            defaults[key] = (parse_default(default_raw), section, i)
    return defaults


def format_val(v) -> str:
    if isinstance(v, str):
        return f'"{v}"'
    return repr(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ui-def", default=r"C:\sd_next_a770\modules\ui_definitions.py",
                    help="Path to SD.Next's modules/ui_definitions.py")
    ap.add_argument("--config", default=r"C:\sd_next_a770\config.json",
                    help="Path to your SD.Next config.json")
    ap.add_argument("--all", action="store_true", help="show all keys, not just changed")
    ap.add_argument("--orphans", action="store_true", help="show config keys missing from source")
    ap.add_argument("--section", help="filter to one section id (e.g. offload, vae_encoder, advanced)")
    args = ap.parse_args()

    ui_def = pathlib.Path(args.ui_def)
    config = pathlib.Path(args.config)
    if not ui_def.exists():
        print(f"ERROR: ui_definitions.py not found: {ui_def}", file=sys.stderr)
        return 2
    if not config.exists():
        print(f"ERROR: config.json not found: {config}", file=sys.stderr)
        return 2

    defaults = scan_ui_definitions(ui_def)
    config_data = json.loads(config.read_text(encoding="utf-8"))

    changed, unchanged, dynamic, orphans = [], [], [], []

    for key, val in config_data.items():
        if key not in defaults:
            orphans.append((key, val))
            continue
        default_val, section, _ = defaults[key]
        if args.section and section != args.section:
            continue
        if default_val == "<dynamic>":
            dynamic.append((key, section, val))
        elif default_val != val:
            changed.append((key, section, val, default_val))
        else:
            unchanged.append((key, section, val))

    if args.orphans:
        print(f"\n=== ORPHAN KEYS (in config.json but not in source) - {len(orphans)} ===")
        for key, val in sorted(orphans):
            print(f"  {key} = {format_val(val)}")
        return 0

    by_section = {}
    for row in changed:
        by_section.setdefault(row[1], []).append(row)

    print(f"\n=== USER-CHANGED SETTINGS - {len(changed)} keys across {len(by_section)} sections ===\n")
    for section in sorted(by_section):
        rows = by_section[section]
        print(f"[{section}]  ({len(rows)} changed)")
        width = max(len(r[0]) for r in rows)
        for key, _, your, default in sorted(rows):
            print(f"  {key:<{width}}  your={format_val(your):<30} default={format_val(default)}")
        print()

    if dynamic:
        print(f"=== KEYS WITH DYNAMIC DEFAULTS (cannot diff) - {len(dynamic)} ===")
        print("(default depends on cmd_opts / platform / device - inspect source line)")
        for key, section, val in sorted(dynamic):
            _, _, lineno = defaults[key]
            print(f"  [{section}] {key} = {format_val(val)}   (ui_definitions.py:{lineno})")
        print()

    if args.all:
        print(f"=== UNCHANGED (matching default) - {len(unchanged)} ===")
        for key, section, val in sorted(unchanged):
            print(f"  [{section}] {key} = {format_val(val)}")
        print()

    print(f"Summary: {len(changed)} changed / {len(dynamic)} dynamic / {len(unchanged)} at-default / {len(orphans)} orphan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
