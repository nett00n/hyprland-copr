#!/usr/bin/env python3
"""Set package release value and optionally lock it.

Usage:
    python3 scripts/set-package-release.py <packages> <release> [--lock]

Arguments:
    packages    Package name(s): single name or comma-separated list (case-insensitive)
    release     Release number (integer)
    --lock      Set release_lock: true to prevent auto-increment (optional)

Examples:
    python3 scripts/set-package-release.py hyprlang 5
    python3 scripts/set-package-release.py hyprlang,hyprutils 5
    python3 scripts/set-package-release.py hyprlang,hyprutils 5 --lock
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml  # noqa: E402
from lib.paths import PACKAGES_YAML  # noqa: E402
from lib.yaml_utils import (  # noqa: E402
    dump_yaml_pretty,
    find_package_name,
    get_packages,
)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    pkg_queries = sys.argv[1]
    release_str = sys.argv[2]
    lock = "--lock" in sys.argv

    # Validate release is integer
    try:
        release_int = int(release_str)
    except ValueError:
        sys.exit(f"error: release must be an integer, got {release_str!r}")

    if release_int < 0:
        sys.exit(f"error: release must be >= 0, got {release_int}")

    # Parse comma-separated package names
    pkg_queries_list = [q.strip() for q in pkg_queries.split(",") if q.strip()]
    if not pkg_queries_list:
        sys.exit("error: no packages specified")

    # Load packages and resolve all names
    all_packages = get_packages()
    resolved_packages: dict[str, str] = {}  # query -> actual_name
    unknown: list[str] = []

    for query in pkg_queries_list:
        pkg_name = find_package_name(all_packages, query)
        if pkg_name is None:
            unknown.append(query)
        else:
            resolved_packages[query] = pkg_name

    if unknown:
        sys.exit(f"error: unknown package(s): {', '.join(unknown)}")

    # Load YAML and update all packages
    data = yaml.safe_load(PACKAGES_YAML.read_text())
    updated: list[tuple[str, int]] = []

    for query, pkg_name in resolved_packages.items():
        if pkg_name not in data:
            sys.exit(f"error: package {pkg_name} not in packages.yaml")

        old_release = data[pkg_name].get("release", 1)
        data[pkg_name]["release"] = release_int

        if lock:
            data[pkg_name]["release_lock"] = True
        else:
            # Remove lock if present (allow auto-management again)
            data[pkg_name].pop("release_lock", None)

        updated.append((pkg_name, old_release))

    # Write back
    PACKAGES_YAML.write_text(dump_yaml_pretty(data))

    # Print results
    if lock:
        status = "release_lock=true"
    else:
        status = "auto-increment enabled"

    for pkg_name, old_release in updated:
        print(f"Set {pkg_name}: release={release_int}, {status}")
        print(f"  (was: {old_release})")

    if len(updated) > 1:
        print(f"\nTotal: {len(updated)} package(s) updated")


if __name__ == "__main__":
    main()
