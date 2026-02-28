#!/usr/bin/env python3
"""Sort string lists in packages.yaml.

Sorts build_requires, requires, and files lists alphabetically within each
package. The packages mapping order is preserved — it is significant for
build-dependency resolution. Lists of dicts (sources, bundled_deps) are
left untouched.

Comment lines within a sorted block are floated to the top of the block.

Usage:
    python3 scripts/sort-yaml-lists.py           # sort in-place
    python3 scripts/sort-yaml-lists.py --dry-run  # preview only
"""

import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not installed — run: pip install -r requirements.txt")

SORTABLE_KEYS: frozenset[str] = frozenset({"build_requires", "requires", "files"})

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_YAML = ROOT / "packages.yaml"


def _item_sort_key(line: str) -> str:
    return line.strip().removeprefix("- ").strip("\"'").lower()


def _sort_block(lines: list[str]) -> list[str]:
    """Sort and deduplicate list items; comment lines float to the top."""
    comments = [ln for ln in lines if ln.strip().startswith("#")]
    items = [ln for ln in lines if not ln.strip().startswith("#")]
    items.sort(key=_item_sort_key)
    seen: set[str] = set()
    deduped: list[str] = []
    for ln in items:
        key = _item_sort_key(ln)
        if key not in seen:
            seen.add(key)
            deduped.append(ln)
    return comments + deduped


def process_content(content: str) -> tuple[str, list[str]]:
    """Return (new_content, sorted_key_names)."""
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    sorted_keys: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match an indented key (at least 1 space) — excludes top-level `packages:`
        m = re.match(r"^( +)([a-z][a-z0-9_]*):\s*\n$", line)
        if m and m.group(2) in SORTABLE_KEYS:
            key = m.group(2)
            item_indent = len(m.group(1)) + 2
            result.append(line)
            i += 1
            block: list[str] = []
            while i < len(lines):
                cur = lines[i]
                raw = cur.rstrip("\n")
                if not raw:
                    break
                if len(raw) - len(raw.lstrip()) < item_indent:
                    break
                block.append(cur)
                i += 1
            sorted_block = _sort_block(block)
            if sorted_block != block:
                sorted_keys.append(key)
            result.extend(sorted_block)
        else:
            result.append(line)
            i += 1
    return "".join(result), sorted_keys


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    if not PACKAGES_YAML.exists():
        sys.exit(f"error: {PACKAGES_YAML} not found")

    content = PACKAGES_YAML.read_text()
    new_content, sorted_keys = process_content(content)

    if not sorted_keys:
        print("Nothing to sort — all lists already sorted.")
        return

    prefix = "[dry-run] " if dry_run else ""
    counts = Counter(sorted_keys)
    print(f"{prefix}Sorted {len(sorted_keys)} list(s):")
    for key, count in sorted(counts.items()):
        print(f"  {key} (×{count})")

    if dry_run:
        return

    try:
        yaml.safe_load(new_content)
    except yaml.YAMLError as exc:
        sys.exit(f"error: result is not valid YAML: {exc}")

    PACKAGES_YAML.write_text(new_content)
    print(f"\nUpdated {PACKAGES_YAML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
