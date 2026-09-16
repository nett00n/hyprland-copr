#!/usr/bin/env python3
"""Stage: Show build plan - display what will run, cache, or skip.

Prints a table showing per-package per-stage status: run, cached, or skipped.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         If set, show only these packages (comma-separated, optional)
  SKIP_PACKAGES   If set, exclude these packages (comma-separated, optional)
  FEDORA_VERSION  Fedora version to target (default: 44)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO       If set, include copr stage in plan (optional)
  FORCE_REBUILD   If '1'/'true', show every requested package's stages as "run"
                  instead of "cache" (mirrors full-cycle.py's FORCE_REBUILD)
"""

import os
import sys

from lib import build_db
from lib.cache import compute_input_hashes
from lib.config import env_flag
from lib.deps import effective_deps, ordered_packages
from lib.paths import resolve_target
from lib.pipeline import STAGE_ORDER, compute_forced_stages, is_cached
from lib.version import VERSION_STAGE_PRECEDENCE, recorded_version
from lib.yaml_utils import STAGES, get_packages


def show_plan(
    package: str = "",
    skip_packages_arg: str = "",
    copr_repo: str = "",
    target: str = "",
    force_packages: set[str] | None = None,
) -> None:
    """Display build plan as a table.

    Uses same cache detection logic as execution:
    - Computes input hashes (source commit, template, config, deps, patches)
    - Checks force_run flags and dependency cascade rules
    - Labels "cache" only if inputs haven't changed AND no forced stages apply
    - force_packages (FORCE_REBUILD) always labels every stage "run", matching
      compute_forced_stages(force_all=True) in full-cycle.py

    Args:
        package: If set, show only these package(s). Comma-separated. If empty, show all.
        skip_packages_arg: If set, exclude these package(s). Comma-separated.
        copr_repo: If set, include copr stage in plan (optional)
        target: build_db target key (mock chroot) to read cached state from
        force_packages: Packages FORCE_REBUILD applies to (see full-cycle.py)
    """
    force_packages = force_packages or set()
    if not target:
        fedora_version = os.environ.get("FEDORA_VERSION", "44")
        target = resolve_target(fedora_version, os.environ.get("MOCK_CHROOT", ""))

    # Load full package set (needed for compute_input_hashes to resolve deps)
    all_packages_full = get_packages()
    # Apply filters for display, in the same topo-sorted, transitive-deps-expanded
    # order the real run (full-cycle.py's prepare_packages()) uses -- required for
    # would_rebuild below to predict a dependency cascade correctly (a dependent
    # must be evaluated after its dependency's outcome is known). See docs/BUGS.md,
    # formerly BUG-0048.
    packages_to_show, _dep_reason = ordered_packages(
        all_packages_full, package, skip_packages_arg
    )

    stages = STAGES if copr_repo else [s for s in STAGES if s != "copr"]

    print("\n=== Build Plan ===")
    print(
        f"  {'package':<30} "
        + "  ".join(f"{s:<8}" for s in stages)
        + f"  {'version':<14}"
    )
    print("  " + "-" * (30 + 14 + 10 * len(stages)))

    # Accumulates across the loop, mirroring full-cycle.py's real-run
    # rebuilt_packages: a dependent evaluated later in topo order sees every
    # dependency that would_rebuild by then, so compute_forced_stages() can
    # predict the cascade rule ("if any dependency was rebuilt this run, force
    # all stages") instead of always seeing an empty set. See docs/BUGS.md,
    # formerly BUG-0048.
    would_rebuild: set[str] = set()

    for pkg in packages_to_show:
        if build_db.get_stage(pkg, "validate", target) is None:
            # No prior validate row -> first run for this package, which will
            # certainly execute every stage. Must still count toward
            # would_rebuild so dependents downstream in topo order cascade.
            would_rebuild.add(pkg)
            continue

        meta = all_packages_full.get(pkg, {})

        # Compute input hashes once per package (used across all stages)
        new_hashes = compute_input_hashes(pkg, meta, all_packages_full)

        # Compute forced stages, threading the accumulated would_rebuild set so a
        # dependency rebuilt earlier in this same loop forces this package too.
        deps = effective_deps(pkg, meta, all_packages_full)
        forced_stages = compute_forced_stages(
            pkg, deps, target, would_rebuild, force_all=pkg in force_packages
        )

        row = []
        pkg_would_rebuild = False
        for stage in stages:
            entry = build_db.get_stage(pkg, stage, target)
            entry_state = entry.get("state") if entry else None

            # Determine label based on state and cache logic
            if entry_state == "skipped":
                label = "skip"
            elif entry_state == "failed":
                label = "retry"
                if stage in STAGE_ORDER:
                    pkg_would_rebuild = True
            elif is_cached(stage, pkg, target, new_hashes, forced_stages):
                label = "cache"
            else:
                label = "run"
                # "validate" is excluded from STAGE_ORDER (lib.pipeline: "all
                # stages except validate, which has no cache") -- it always
                # shows "run" here (stage-validate.py has no caching, full-cycle.py
                # never adds to rebuilt_packages for it), and must not count
                # toward would_rebuild or every dependent would falsely cascade
                # on every run, cached or not. See docs/BUGS.md, formerly BUG-0048.
                if stage in STAGE_ORDER:
                    pkg_would_rebuild = True

            row.append(f"{label:<8}")

        if pkg_would_rebuild:
            would_rebuild.add(pkg)

        version = recorded_version(
            [build_db.get_stage(pkg, s, target) for s in VERSION_STAGE_PRECEDENCE],
            meta,
        )
        print(f"  {pkg:<30} " + "  ".join(row) + f"  {version:<14}")

    print()


if __name__ == "__main__":
    try:
        package = os.environ.get("PACKAGE", "")
        skip_packages_arg = os.environ.get("SKIP_PACKAGES", "")
        copr_repo = os.environ.get("COPR_REPO", "")
        force_packages: set[str] = set()
        if env_flag("FORCE_REBUILD"):
            force_packages = (
                {n.strip() for n in package.split(",") if n.strip()}
                if package
                else set(get_packages())
            )
        show_plan(package, skip_packages_arg, copr_repo, force_packages=force_packages)
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
