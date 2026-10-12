#!/usr/bin/env python3
"""List all tags for upstreams, highlighting the latest semver tag.

Usage:
    python3 scripts/list-tags.py               # all upstreams
    python3 scripts/list-tags.py hyprpicker    # one upstream
"""

import argparse
import sys

from lib.paths import PACKAGES_YAML
from lib.upstream import fetch_tags, list_upstreams, resolve_module
from lib.version import latest_semver
from lib.yaml_utils import get_packages


def cmd_list_tags(modules: list[dict]) -> None:
    """Print all tags for each upstream, marking the detected latest."""
    for mod in modules:
        name = mod["name"]
        url = mod["url"]
        print(f"fetching tags: {name} ...", file=sys.stderr)
        tags, _error = fetch_tags(url)
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
        description="List all tags for upstreams, highlighting the latest semver."
    )
    parser.add_argument(
        "package",
        nargs="?",
        metavar="PACKAGE",
        help="limit to this upstream (matches last path component, e.g. hyprpicker)",
    )
    args = parser.parse_args()

    if not PACKAGES_YAML.exists():
        print(f"error: {PACKAGES_YAML} not found", file=sys.stderr)
        sys.exit(1)

    modules = list_upstreams(get_packages(PACKAGES_YAML))

    if args.package:
        mod = resolve_module(modules, args.package)
        if mod is None:
            print(
                f"error: upstream '{args.package}' not found in packages.yaml urls",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd_list_tags([mod])
    else:
        cmd_list_tags(modules)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
