#!/usr/bin/env python3
"""Full build cycle orchestrator: spec → srpm → mock → copr.

Delegates each stage to the appropriate stage-*.py script, then
prints a summary table. All state is recorded in build-report.db.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  FEDORA_VERSION             Fedora version to target (default: 43)
  MOCK_CHROOT                Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO                  Copr repo slug, e.g. nett00n/hyprland (optional)
  PACKAGE                    Build only this package (optional, comma-separated)
  SKIP_PACKAGES              Skip these packages (optional, comma-separated)
  PROCEED_BUILD              If 'true', skip stages already succeeded; preserve prior state
  FORCE_REBUILD              If '1'/'true', ignore the cache and re-run every stage
                              (spec through copr) for the requested PACKAGE(s) -- or every
                              package if PACKAGE is unset. Wins over PROCEED_BUILD for the
                              affected packages. Deps pulled in transitively still respect
                              the cache; use `make build-pop` for a mock/copr-only force.
  SKIP_MOCK                  If 'true', skip mock build stage
  SKIP_COPR                  If 'true', skip copr submission stage
  SYNCHRONOUS_COPR_BUILD     If 'true', wait for COPR builds; default is async (--nowait)
  REQUIRE_CHROOT_COVERAGE    If 'true', block Copr submission instead of warning when a
                             chroot has no verified local mock build (see docs/bugs.md
                             BUG-0018). Default: warn and submit anyway.
  LOG_LEVEL                  Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import importlib
import os
import shutil
import sys
import time

from lib import build_db
from lib.cache import compute_input_hashes
from lib.config import env_flag
from lib.copr import print_chroot_coverage
from lib.deps import build_dep_graph, effective_deps, topological_sort, transitive_deps
from lib.gitmodules import ensure_initialized, parse_gitmodules
from lib.log_analysis import report_mock_failures, report_copr_failures
from lib.pipeline import (
    compute_forced_stages,
    is_cached,
    cache_miss_reason,
)
from lib.paths import (
    ARCH,
    BUILD_LOG_DIR,
    DISTRO,
    GITMODULES,
    ROOT,
    get_package_log_dir,
    resolve_target,
)
from lib.reporting import print_summary
from lib.source_lock import missing_entries
from lib.yaml_utils import (
    STAGES,
    SUPPORTED_FEDORA_VERSIONS,
    filter_packages,
    get_packages,
    skip_packages,
    update_package_releases,
)

PYTHON = sys.executable

# Import stage scripts using importlib (dashes in names)
_stage = {
    name: importlib.import_module(name)
    for name in [
        "stage-validate",
        "stage-show-plan",
        "stage-spec",
        "stage-vendor",
        "stage-srpm",
        "stage-mock",
        "stage-copr",
        "refresh-checksums",
    ]
}


def preflight_autoheal(packages: dict) -> None:
    """Auto-fix two known "forgot a manual step" causes of pipeline failure
    before the per-package loop even starts (TODO-0072):

    - A package's git submodule was never checked out (fresh clone without
      --recurse-submodules, or newly added via add-new/add-submodule and never
      pulled) -- init it in place via `git submodule update --init`.
    - A package has a remote source with no entry in sources.lock.yaml yet
      (newly scaffolded/added package, refresh-checksums never run) -- record
      it now instead of letting stage-srpm fail closed on it (BUG-0025).

    Both are idempotent no-ops when there's nothing to fix, so this is safe to
    run unconditionally on every full-cycle invocation.
    """
    if GITMODULES.exists():
        modules = parse_gitmodules(GITMODULES)
        urls = {meta.get("url", "") for meta in packages.values() if meta.get("url")}
        pulled = ensure_initialized(ROOT, modules, urls)
        if pulled:
            print(f"\nAuto-initialized submodules: {', '.join(pulled)}")

    stale = missing_entries(packages)
    if stale:
        print(f"\nAuto-refreshing checksums for: {', '.join(stale)}")
        stale_packages = {pkg: packages[pkg] for pkg in stale}
        if not _stage["refresh-checksums"].refresh(stale_packages, force=False):
            sys.exit("error: auto checksum refresh failed -- see output above")


def print_proceed_status(packages: dict, target: str, copr_repo: str) -> None:
    """Print per-package per-stage status when resuming with PROCEED_BUILD=true."""
    stages = STAGES if copr_repo else [s for s in STAGES if s != "copr"]
    status_label = {"success": "skip", "failed": "retry", None: "run"}
    print("\nPROCEED_BUILD=true — resuming from prior build state")
    print(f"  {'package':<30} " + "  ".join(f"{s:<8}" for s in stages))
    print("  " + "-" * (30 + 10 * len(stages)))
    for pkg in packages:
        row = []
        for stage in stages:
            entry = build_db.get_stage(pkg, stage, target)
            state = entry.get("state") if entry else None
            label = status_label.get(state, state or "run")
            row.append(f"{label:<8}")
        print(f"  {pkg:<30} " + "  ".join(row))
    print()


def load_config() -> tuple[str, str, str, str, str, bool, bool, bool, bool]:
    """Load environment variables.

    Returns (fedora_version, target, copr_repo, package_filter, skip_filter, skip_mock,
    skip_copr, synchronous_copr, force_rebuild).
    """
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    if fedora_version not in SUPPORTED_FEDORA_VERSIONS:
        sys.exit(
            f"error: unsupported FEDORA_VERSION={fedora_version!r}, "
            f"expected one of {sorted(SUPPORTED_FEDORA_VERSIONS)}"
        )
    target = resolve_target(fedora_version, os.environ.get("MOCK_CHROOT", ""))
    copr_repo = os.environ.get("COPR_REPO", "")
    package_filter = os.environ.get("PACKAGE", "")
    skip_filter = os.environ.get("SKIP_PACKAGES", "")
    skip_mock = os.environ.get("SKIP_MOCK", "").lower() == "true"
    skip_copr = os.environ.get("SKIP_COPR", "").lower() == "true"
    synchronous_copr = os.environ.get("SYNCHRONOUS_COPR_BUILD", "").lower() == "true"
    force_rebuild = env_flag("FORCE_REBUILD")
    if force_rebuild and env_flag("PROCEED_BUILD"):
        print(
            "warning: FORCE_REBUILD=1 and PROCEED_BUILD=true both set -- "
            "FORCE_REBUILD wins for the affected package(s)",
            file=sys.stderr,
        )
    return (
        fedora_version,
        target,
        copr_repo,
        package_filter,
        skip_filter,
        skip_mock,
        skip_copr,
        synchronous_copr,
        force_rebuild,
    )


def prepare_packages(package_filter: str, skip_filter: str) -> dict:
    """Load, sort, filter, and expand packages with transitive dependencies.

    Always applies topological sort to ensure correct build order.
    For selective builds (PACKAGE=), also expands transitive dependencies.
    """
    all_packages = get_packages()

    graph = build_dep_graph(all_packages)
    try:
        order = topological_sort(graph)
    except ValueError as e:
        sys.exit(f"error: {e}")

    # Rebuild all_packages in topological order
    sorted_packages = {k: all_packages[k] for k in order}
    packages = filter_packages(sorted_packages, package_filter)
    packages = skip_packages(packages, skip_filter)

    if package_filter:
        # Expand transitive deps for selective build
        expanded: dict = {}
        dep_reason: dict[str, str] = {}
        for name in list(packages):
            for dep in transitive_deps(name, graph):
                if dep not in expanded:
                    expanded[dep] = all_packages[dep]
                    dep_reason[dep] = name
            expanded[name] = all_packages[name]
        requested = {n.strip() for n in package_filter.split(",") if n.strip()}
        # Re-sort the expanded set (preserve topological order)
        packages = {k: expanded[k] for k in order if k in expanded}
        print(f"\nPackage build plan ({len(packages)} total):")
        for pkg in packages:
            reason = (
                "" if pkg in requested else f"  (dep of {dep_reason.get(pkg, '?')})"
            )
            print(f"  {pkg}{reason}")

    return packages


def resolve_force_packages(
    force_rebuild: bool, package_filter: str, packages: dict
) -> set[str]:
    """Resolve which packages FORCE_REBUILD applies to.

    Scoped to the explicitly-requested packages only -- transitive deps pulled into
    the run by `prepare_packages()` still respect the cache. If PACKAGE is unset,
    every package in the run is "requested", so force applies to all of them.
    """
    if not force_rebuild:
        return set()
    if package_filter:
        requested = {n.strip() for n in package_filter.split(",") if n.strip()}
        return requested & set(packages)
    return set(packages)


def setup_run(
    packages: dict,
    target: str,
    fedora_version: str,
    copr_repo: str,
    package_filter: str,
) -> int:
    """Print resume status (if applicable) and start a new run. Returns run_id."""
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    if proceed:
        print_proceed_status(packages, target, copr_repo)

    return build_db.start_run(
        target, DISTRO, fedora_version, ARCH, copr_repo, package_filter
    )


def mock_failed_packages(packages: dict, target: str) -> list[str]:
    """Return names of packages whose mock stage ended this run in a "failed" state.

    Used to gate Copr submission on the whole run, not just the failed package:
    per-package pipelines used to submit each package to Copr as soon as its
    own mock succeeded, so a healthy early package (e.g. hyprutils) could
    already be public on Copr by the time a later, dependent package (e.g.
    Hyprland) failed mock -- publishing a dependency set that doesn't
    actually work together. See docs/bugs.md / issue #8.
    """
    return sorted(
        pkg
        for pkg in packages
        if (build_db.get_stage(pkg, "mock", target) or {}).get("state") == "failed"
    )


def run_build_pipeline(
    packages: dict,
    target: str,
    run_id: int,
    fedora_version: str,
    copr_repo: str,
    proceed: bool,
    skip_mock: bool = False,
    skip_copr: bool = False,
    synchronous_copr: bool = False,
    force_packages: set[str] | None = None,
) -> None:
    """Run per-package pipeline orchestration: validate→spec→vendor→srpm→mock, then copr.

    Each package goes through validate/spec/vendor/srpm/mock before moving to the
    next package. Per-package skip-on-failure enables faster feedback and independent
    tracking. Tracks rebuilt packages to cascade forced stages to dependents.
    Respects skip_mock and skip_copr flags to skip those stages entirely.

    force_packages (FORCE_REBUILD): packages in this set get every stage forced
    (compute_forced_stages(force_all=True)) and also have PROCEED_BUILD ignored for
    themselves specifically, so an explicit force always wins over a stale "already
    succeeded" resume.

    Copr submission runs as a separate pass AFTER every package has gone through
    mock, and is skipped entirely (for every package) if any package's mock stage
    failed this run -- a broken dependency set must never be partially published.

    If synchronous_copr is False (default), COPR builds use --nowait for async submission.
    """
    force_packages = force_packages or set()
    all_packages = get_packages()

    # Show plan first, before any processing
    _stage["stage-show-plan"].show_plan(
        copr_repo=copr_repo, target=target, force_packages=force_packages
    )
    print("  waiting 5 seconds before proceeding...", flush=True)
    time.sleep(5)

    # Global checks: run once before the per-package loop
    _stage["stage-validate"].run_global_checks(all_packages)

    if copr_repo:
        # FIXME(BUG-0036): return value is discarded, and validate_copr_repo()
        # is never called here -- a bad COPR_REPO/token only fails after the
        # full build. See docs/bugs.md.
        _stage["stage-copr"].check_copr_credentials()

    mock_failed: dict[str, bool] = {}
    rebuilt_packages: set[str] = set()

    print("\n=== Full Cycle (Per-Package) ===")
    for pkg, meta in packages.items():
        print(f"\n  {pkg}:")

        # Compute input hashes once per package
        new_hashes = compute_input_hashes(pkg, meta, all_packages)

        # Resolve effective dependencies once per package
        deps = effective_deps(pkg, meta, all_packages)

        # FORCE_REBUILD for this package wins over a PROCEED_BUILD resume.
        pkg_proceed = proceed and pkg not in force_packages

        # Compute forced stages (from FORCE_REBUILD, force_run, or dependency cascade)
        forced_stages = compute_forced_stages(
            pkg, deps, target, rebuilt_packages, force_all=pkg in force_packages
        )

        # Validate (non-fatal, no caching)
        if not _stage["stage-validate"].run_for_package(
            pkg, meta, all_packages, fedora_version, target, run_id
        ):
            print(f"    warning: validate failed for {pkg}", file=sys.stderr)
            # non-fatal: continue to spec (matches current behaviour)

        # Spec
        if is_cached("spec", pkg, target, new_hashes, forced_stages):
            print("    spec: cached")
            build_db.update_reason(pkg, "spec", target, "cached")
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_entry = build_db.get_stage(pkg, "spec", target)
            prior_state = prior_entry.get("state") if prior_entry else None
            is_proceed_skip = pkg_proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "spec",
                    pkg,
                    target,
                    new_hashes,
                    forced_stages,
                    deps,
                    rebuilt_packages,
                )
            )
            if not _stage["stage-spec"].run_for_package(
                pkg, meta, all_packages, fedora_version, target, run_id
            ):
                build_db.finalize_stage(
                    pkg,
                    "spec",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )
                # Skip downstream stages unless any are forced
                if not any(
                    s in forced_stages for s in ["vendor", "srpm", "mock", "copr"]
                ):
                    continue
            else:
                build_db.finalize_stage(
                    pkg,
                    "spec",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )

        # Vendor
        vendor_entry = build_db.get_stage(pkg, "vendor", target) or {}
        if vendor_entry.get("state") == "skipped" or is_cached(
            "vendor", pkg, target, new_hashes, forced_stages
        ):
            print("    vendor: cached")
            if vendor_entry:
                build_db.update_reason(pkg, "vendor", target, "cached")
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_state = vendor_entry.get("state") if vendor_entry else None
            is_proceed_skip = pkg_proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "vendor",
                    pkg,
                    target,
                    new_hashes,
                    forced_stages,
                    deps,
                    rebuilt_packages,
                )
            )
            result = _stage["stage-vendor"].run_for_package(
                pkg, meta, fedora_version, target, run_id, all_packages
            )
            if result is False:
                build_db.finalize_stage(
                    pkg,
                    "vendor",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )
                # Skip downstream stages unless any are forced
                if not any(s in forced_stages for s in ["srpm", "mock", "copr"]):
                    continue
            else:
                build_db.finalize_stage(
                    pkg,
                    "vendor",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )

        # SRPM
        if is_cached("srpm", pkg, target, new_hashes, forced_stages):
            print("    srpm: cached")
            build_db.update_reason(pkg, "srpm", target, "cached")
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_entry = build_db.get_stage(pkg, "srpm", target)
            prior_state = prior_entry.get("state") if prior_entry else None
            is_proceed_skip = pkg_proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "srpm",
                    pkg,
                    target,
                    new_hashes,
                    forced_stages,
                    deps,
                    rebuilt_packages,
                )
            )
            if not _stage["stage-srpm"].run_for_package(
                pkg, meta, fedora_version, pkg_proceed, target, run_id
            ):
                build_db.finalize_stage(
                    pkg,
                    "srpm",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )
                # Skip downstream stages unless any are forced
                if not any(s in forced_stages for s in ["mock", "copr"]):
                    continue
            else:
                build_db.finalize_stage(
                    pkg,
                    "srpm",
                    target,
                    started_at,
                    new_hashes,
                    reason=reason,
                    update_hashes=not is_proceed_skip,
                )

        # Mock
        if skip_mock:
            print("    mock: skipped (SKIP_MOCK=true)")
            build_db.update_reason(pkg, "mock", target, "SKIP_MOCK")
        else:
            if is_cached("mock", pkg, target, new_hashes, forced_stages):
                print("    mock: cached")
                build_db.update_reason(pkg, "mock", target, "cached")
            else:
                rebuilt_packages.add(pkg)
                started_at = int(time.time())
                prior_entry = build_db.get_stage(pkg, "mock", target)
                prior_state = prior_entry.get("state") if prior_entry else None
                is_proceed_skip = pkg_proceed and prior_state == "success"
                reason = (
                    "proceed-skip"
                    if is_proceed_skip
                    else cache_miss_reason(
                        "mock",
                        pkg,
                        target,
                        new_hashes,
                        forced_stages,
                        deps,
                        rebuilt_packages,
                    )
                )
                if not _stage["stage-mock"].run_for_package(
                    pkg,
                    meta,
                    fedora_version,
                    target,
                    pkg_proceed,
                    mock_failed,
                    packages,
                    run_id,
                ):
                    build_db.finalize_stage(
                        pkg,
                        "mock",
                        target,
                        started_at,
                        new_hashes,
                        reason=reason,
                        update_hashes=not is_proceed_skip,
                    )
                else:
                    build_db.finalize_stage(
                        pkg,
                        "mock",
                        target,
                        started_at,
                        new_hashes,
                        reason=reason,
                        update_hashes=not is_proceed_skip,
                    )

    # Copr: a separate pass, only after every package has gone through mock.
    # If anything failed mock this run, no package is submitted -- see
    # mock_failed_packages() docstring.
    blockers = (
        [] if skip_copr or not copr_repo else mock_failed_packages(packages, target)
    )
    if blockers:
        print(
            f"\n  ✗ mock failed for: {', '.join(blockers)} -- "
            "skipping Copr submission for all packages this run",
            file=sys.stderr,
        )

    # Pre-submission chroot coverage gate (docs/bugs.md BUG-0018): warns by
    # default, blocks (like the mock-failure `blockers` case above) only under
    # REQUIRE_CHROOT_COVERAGE=true.
    coverage_blocked = False
    if not skip_copr and copr_repo and not blockers:
        require_coverage = (
            os.environ.get("REQUIRE_CHROOT_COVERAGE", "").lower() == "true"
        )
        covered = print_chroot_coverage(copr_repo, packages)
        if not covered and require_coverage:
            coverage_blocked = True
            print(
                "\n  ✗ REQUIRE_CHROOT_COVERAGE=true and some chroots lack a "
                "verified local mock build -- skipping Copr submission for "
                "all packages this run (see docs/bugs.md BUG-0018)",
                file=sys.stderr,
            )

    print("\n=== Full Cycle (Per-Package): Copr ===")
    for pkg, meta in packages.items():
        print(f"\n  {pkg}:")

        if skip_copr:
            print("    copr: skipped (SKIP_COPR=true)")
            build_db.update_reason(pkg, "copr", target, "SKIP_COPR")
            continue

        if not copr_repo:
            continue

        if blockers:
            print(f"    copr: blocked (mock failed for {', '.join(blockers)})")
            # state=skipped, matching every other upstream-failure skip case
            # in the pipeline (e.g. "spec failed", "srpm failed").
            build_db.set_stage(
                pkg,
                "copr",
                target,
                run_id,
                "skipped",
                reason=f"blocked: mock failed for {', '.join(blockers)}",
            )
            continue

        if coverage_blocked:
            print("    copr: blocked (chroot coverage)")
            build_db.set_stage(
                pkg,
                "copr",
                target,
                run_id,
                "skipped",
                reason="blocked: chroot coverage",
            )
            continue

        new_hashes = compute_input_hashes(pkg, meta, all_packages)
        deps = effective_deps(pkg, meta, all_packages)
        pkg_proceed = proceed and pkg not in force_packages
        forced_stages = compute_forced_stages(
            pkg, deps, target, rebuilt_packages, force_all=pkg in force_packages
        )

        if is_cached("copr", pkg, target, new_hashes, forced_stages):
            print("    copr: cached")
            build_db.update_reason(pkg, "copr", target, "cached")
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_entry = build_db.get_stage(pkg, "copr", target)
            prior_state = prior_entry.get("state") if prior_entry else None
            is_proceed_skip = pkg_proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "copr",
                    pkg,
                    target,
                    new_hashes,
                    forced_stages,
                    deps,
                    rebuilt_packages,
                )
            )
            success = _stage["stage-copr"].run_for_package(
                pkg,
                meta,
                fedora_version,
                copr_repo,
                pkg_proceed,
                target,
                run_id,
                synchronous_copr,
            )
            build_db.finalize_stage(
                pkg,
                "copr",
                target,
                started_at,
                new_hashes,
                reason=reason,
                update_hashes=not is_proceed_skip and success,
            )


def finalize_report(
    packages: dict,
    target: str,
    run_id: int,
    copr_repo: str,
    synchronous_copr: bool = False,
) -> None:
    """Print summary, finish the run, and exit if any failed.

    When SYNCHRONOUS_COPR_BUILD=false, 'unknown' states in copr stage are valid (builds pending).
    Only fail if there are actual 'failed' states in non-copr stages or in copr when synchronous.

    Scoped to `packages` (this run's package set) -- unlike the old
    finalize_report(), which scanned the WHOLE persisted report and so one
    stale failed row from an unrelated package made every future run exit
    non-zero (see docs/bugs.md / issue #23).
    """
    stages = build_db.stage_map(target)
    print_summary(packages, stages, copr_repo)

    any_failed = any(
        (stages.get(stage_name, {}).get(pkg) or {}).get("state") == "failed"
        for pkg in packages
        for stage_name in STAGES
        if stage_name not in ("validate", "copr")
        or (stage_name == "copr" and synchronous_copr)
    )

    build_db.finish_run(run_id, "failed" if any_failed else "ok")
    print(f"\nBuild recorded in build-report.db (run {run_id})")

    # Analyze mock failures if present
    mock_failures = [
        pkg
        for pkg in packages
        if (stages.get("mock", {}).get(pkg) or {}).get("state") == "failed"
    ]
    if mock_failures:
        report_mock_failures(packages, BUILD_LOG_DIR)

    # Analyze copr failures if present. Only meaningful in synchronous mode --
    # async submissions are still "unknown"/pending here and only reach a
    # terminal "failed" state later, when gen-report.py polls (see
    # lib.copr.poll_copr_status, which fetches the failed chroots' logs at
    # that point; `make stage-log-analyze` picks them up once they land).
    if synchronous_copr:
        copr_failures = [
            pkg
            for pkg in packages
            if (stages.get("copr", {}).get(pkg) or {}).get("state") == "failed"
        ]
        if copr_failures:
            report_copr_failures(packages, BUILD_LOG_DIR)

    if any_failed:
        sys.exit(1)


def main() -> None:
    (
        fedora_version,
        target,
        copr_repo,
        package_filter,
        skip_filter,
        skip_mock,
        skip_copr,
        synchronous_copr,
        force_rebuild,
    ) = load_config()

    packages = prepare_packages(package_filter, skip_filter)
    if not packages:
        sys.exit("error: no packages to build")

    preflight_autoheal(packages)

    BUILD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    for pkg in packages:
        pkg_log_dir = get_package_log_dir(pkg)
        if pkg_log_dir.exists():
            try:
                shutil.rmtree(pkg_log_dir)
            except OSError as e:
                print(f"warning: could not remove {pkg_log_dir}: {e}", file=sys.stderr)

    run_id = setup_run(packages, target, fedora_version, copr_repo, package_filter)

    # Pre-build: auto-increment/reset release values
    release_updates = update_package_releases(packages, target)
    if release_updates:
        print(f"\nRelease updates: {release_updates}")
        # Reload packages to pick up updated release values
        packages = prepare_packages(package_filter, skip_filter)

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    force_packages = resolve_force_packages(force_rebuild, package_filter, packages)
    if force_packages:
        print(f"\nFORCE_REBUILD: forcing every stage for {', '.join(force_packages)}")

    run_build_pipeline(
        packages,
        target,
        run_id,
        fedora_version,
        copr_repo,
        proceed,
        skip_mock,
        skip_copr,
        synchronous_copr,
        force_packages,
    )
    finalize_report(packages, target, run_id, copr_repo, synchronous_copr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
