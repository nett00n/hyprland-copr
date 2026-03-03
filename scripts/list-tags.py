#!/usr/bin/env python3
"""List all tags for submodules, highlighting the latest semver tag.

Usage:
    python3 scripts/list-tags.py               # all submodules
    python3 scripts/list-tags.py hyprpicker    # one submodule
"""

import argparse
import sys

from lib.gitmodules import fetch_tags, parse_gitmodules, resolve_module
from lib.paths import GITMODULES
from lib.version import latest_semver


def cmd_list_tags(modules: list[dict]) -> None:
    """Print all tags for each submodule, marking the detected latest."""
    for mod in modules:
        name = mod["name"]
        url = mod["url"]
        print(f"fetching tags: {name} ...", file=sys.stderr)
        tags = fetch_tags(url)
        detected = latest_semver(tags)
        print(f"\n{name}  ({url})")
        if not tags:
            print("  (no tags found)")
            continue
        for tag in sorted(tags):
            marker = "  <- latest" if tag == detected else ""
            print(f"  {tag}{marker}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List all tags for submodules, highlighting the latest semver."
    )
    parser.add_argument(
        "package",
        nargs="?",
        metavar="PACKAGE",
        help="limit to this submodule (matches last path component, e.g. hyprpicker)",
    )
    args = parser.parse_args()

    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)

    if args.package:
        mod = resolve_module(modules, args.package)
        if mod is None:
            print(
                f"error: submodule '{args.package}' not found in .gitmodules",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd_list_tags([mod])
    else:
        cmd_list_tags(modules)


if __name__ == "__main__":
    main()
