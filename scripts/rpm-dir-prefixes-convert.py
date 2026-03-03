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
import re
import sys

import yaml

from lib.paths import PACKAGES_YAML, ROOT
from lib.rpm_macros import normalize_file_entry


def iter_file_lists(data: dict):
    """Yield every list from any `files:` key in the packages tree."""
    for pkg in data.get("packages", {}).values():
        if "files" in pkg:
            yield pkg["files"]
        if devel := pkg.get("devel"):
            if "files" in devel:
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


def apply_replacements(content: str, replacements: dict[str, str]) -> str:
    """Replace each old entry with the normalized form in the raw YAML text."""
    for old, new in replacements.items():
        content = content.replace(f'"{old}"', f'"{new}"')
        content = content.replace(f"'{old}'", f"'{new}'")
        content = re.sub(
            r"(^\s*-\s+)" + re.escape(old) + r"(\s*)$",
            r"\g<1>" + new + r"\g<2>",
            content,
            flags=re.MULTILINE,
        )
    return content


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

    content = PACKAGES_YAML.read_text()
    data = yaml.safe_load(content)

    replacements = collect_replacements(data, args.reverse)

    direction = "macros -> absolute" if args.reverse else "absolute -> macros"
    if not replacements:
        print(f"Nothing to normalize ({direction}) — no matching paths found.")
        return

    print(f"Direction: {direction}\n")
    for old, new in replacements.items():
        print(f"  {old!r}")
        print(f"    -> {new!r}")

    new_content = apply_replacements(content, replacements)

    if args.dry_run:
        print("\n[dry-run] No changes written.")
        return

    PACKAGES_YAML.write_text(new_content)
    print(f"\nUpdated {PACKAGES_YAML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
