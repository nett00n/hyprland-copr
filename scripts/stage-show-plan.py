#!/usr/bin/env python3
"""Stage: Show build plan - display what will run, cache, or skip.

Prints a table showing per-package per-stage status: run, cached, or skipped.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         If set, show only these packages (comma-separated, optional)
  SKIP_PACKAGES   If set, exclude these packages (comma-separated, optional)
  COPR_REPO       If set, include copr stage in plan (optional)
"""

import os
import sys

from lib.cache import compute_input_hashes
from lib.pipeline import compute_forced_stages, is_cached
from lib.yaml_utils import (
    STAGES,
    filter_packages,
    get_packages,
    load_build_status,
    skip_packages,
)


def show_plan(
    package: str = "", skip_packages_arg: str = "", copr_repo: str = ""
) -> None:
    """Display build plan as a table.

    Uses same cache detection logic as execution:
    - Computes input hashes (source commit, template, config, deps, patches)
    - Checks force_run flags and dependency cascade rules
    - Labels "cache" only if inputs haven't changed AND no forced stages apply

    Args:
        package: If set, show only these package(s). Comma-separated. If empty, show all.
        skip_packages_arg: If set, exclude these package(s). Comma-separated.
        copr_repo: If set, include copr stage in plan (optional)
    """
    try:
        build_status = load_build_status()
    except FileNotFoundError:
        print(
            "error: build-report.yaml not found (run after validate stage)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load full package set (needed for compute_input_hashes to resolve deps)
    all_packages_full = get_packages()
    # Apply filters for display
    packages_to_show = filter_packages(all_packages_full, package)
    packages_to_show = skip_packages(packages_to_show, skip_packages_arg)

    stages = STAGES if copr_repo else [s for s in STAGES if s != "copr"]

    print("\n=== Build Plan ===")
    print(f"  {'package':<30} " + "  ".join(f"{s:<8}" for s in stages))
    print("  " + "-" * (30 + 10 * len(stages)))

    for pkg in packages_to_show:
        if pkg not in build_status.get("stages", {}).get("validate", {}):
            continue

        meta = all_packages_full.get(pkg, {})

        # Compute input hashes once per package (used across all stages)
        new_hashes = compute_input_hashes(pkg, meta, all_packages_full)

        # Compute forced stages (note: during planning, no packages have been rebuilt yet)
        forced_stages = compute_forced_stages(pkg, meta, build_status, set())

        row = []
        for stage in stages:
            entry_state = (
                build_status.get("stages", {}).get(stage, {}).get(pkg, {}).get("state")
            )

            # Determine label based on state and cache logic
            if entry_state == "skipped":
                label = "skip"
            elif entry_state == "failed":
                label = "retry"
            elif is_cached(stage, pkg, build_status, new_hashes, forced_stages):
                label = "cache"
            else:
                label = "run"

            row.append(f"{label:<8}")

        print(f"  {pkg:<30} " + "  ".join(row))

    print()


if __name__ == "__main__":
    package = os.environ.get("PACKAGE", "")
    skip_packages_arg = os.environ.get("SKIP_PACKAGES", "")
    copr_repo = os.environ.get("COPR_REPO", "")
    show_plan(package, skip_packages_arg, copr_repo)
