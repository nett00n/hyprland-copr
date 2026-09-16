#!/usr/bin/env python3
"""Normalize paths in packages.yaml files sections between absolute paths and RPM macros.

By default converts absolute paths -> RPM macros.
Use --reverse to convert RPM macros -> absolute paths.

Usage:
    python3 scripts/rpm-dir-prefixes-convert.py                   # abs -> macros
    python3 scripts/rpm-dir-prefixes-convert.py --reverse         # macros -> abs
    python3 scripts/rpm-dir-prefixes-convert.py --dry-run         # preview only
    python3 scripts/rpm-dir-prefixes-convert.py --reverse --dry-run
"""

import argparse
import sys
from collections.abc import Iterator

import yaml

from lib.paths import PACKAGES_YAML, ROOT
from lib.rpm_macros import normalize_file_entry
from lib.yaml_utils import write_yaml_file


def iter_file_lists(data: dict) -> Iterator[list]:
    """Yield every list from any `files:` key in the packages tree."""
    packages = data.get("packages", data) if "packages" in data else data
    for pkg in packages.values():
        if "files" in pkg:
            yield pkg["files"]
        if (devel := pkg.get("devel")) and "files" in devel:
            yield devel["files"]


def collect_replacements(data: dict, reverse: bool) -> dict[str, str]:
    """Return a mapping of original entry -> normalized entry for changed entries."""
    replacements: dict[str, str] = {}
    for file_list in iter_file_lists(data):
        for entry in file_list or []:
            if entry is None:
                continue
            normalized = normalize_file_entry(entry, reverse)
            if normalized != entry:
                replacements[entry] = normalized
    return replacements


def apply_replacements(data: dict, reverse: bool) -> int:
    """Normalize every `files:` entry in place. Returns the count changed.

    Mutates the parsed tree directly instead of splicing the raw YAML text:
    a raw-text replace isn't scoped to `files:` lists, so a `files:` entry
    that happens to also appear (as a substring or a whole other list item)
    in `requires:`, `build.install`, etc. would get rewritten too, and a bad
    substitution would ship to disk with no re-parse to catch it.
    """
    changed = 0
    for file_list in iter_file_lists(data):
        for i, entry in enumerate(file_list or []):
            if entry is None:
                continue
            normalized = normalize_file_entry(entry, reverse)
            if normalized != entry:
                file_list[i] = normalized
                changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize file paths in packages.yaml between absolute paths and RPM macros."
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="convert RPM macros -> absolute paths (default: abs -> macros)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without writing",
    )
    args = parser.parse_args()

    if not PACKAGES_YAML.exists():
        sys.exit(f"error: {PACKAGES_YAML} not found")

    data = yaml.safe_load(PACKAGES_YAML.read_text())

    replacements = collect_replacements(data, args.reverse)

    direction = "macros -> absolute" if args.reverse else "absolute -> macros"
    if not replacements:
        print(f"Nothing to normalize ({direction}) — no matching paths found.")
        return

    print(f"Direction: {direction}\n")
    for old, new in replacements.items():
        print(f"  {old!r}")
        print(f"    -> {new!r}")

    if args.dry_run:
        print("\n[dry-run] No changes written.")
        return

    apply_replacements(data, args.reverse)

    write_yaml_file(PACKAGES_YAML, data)
    print(f"\nUpdated {PACKAGES_YAML.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
