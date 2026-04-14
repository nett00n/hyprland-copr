#!/usr/bin/env python3
"""Full build cycle orchestrator: spec → srpm → mock → copr.

Delegates each stage to the appropriate stage-*.py script, then
prints a summary table and writes build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  FEDORA_VERSION             Fedora version to target (default: 43)
  MOCK_CHROOT                Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO                  Copr repo slug, e.g. nett00n/hyprland (optional)
  PACKAGE                    Build only this package (optional, comma-separated)
  SKIP_PACKAGES              Skip these packages (optional, comma-separated)
  PROCEED_BUILD              If 'true', skip stages already succeeded; preserve build-report.yaml
  SKIP_MOCK                  If 'true', skip mock build stage
  SKIP_COPR                  If 'true', skip copr submission stage
  SYNCHRONOUS_COPR_BUILD     If 'true', wait for COPR builds; default is async (--nowait)
  LOG_LEVEL                  Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import importlib
import os
import shutil
import sys
import time
from datetime import datetime, timezone

from lib.cache import compute_input_hashes
from lib.deps import build_dep_graph, topological_sort, transitive_deps
from lib.log_analysis import report_mock_failures
from lib.pipeline import (
    compute_forced_stages,
    inject_stage_meta,
    is_cached,
    cache_miss_reason,
)
from lib.paths import BUILD_LOG_DIR, ROOT, get_package_log_dir, mock_chroot
from lib.reporting import print_summary
from lib.yaml_utils import (
    BUILD_STATUS_YAML,
    STAGES,
    SUPPORTED_FEDORA_VERSIONS,
    dump_yaml_pretty,
    filter_packages,
    get_packages,
    load_build_status,
    save_build_status,
    skip_packages,
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
    ]
}


def print_proceed_status(packages: dict, build_status: dict, copr_repo: str) -> None:
    """Print per-package per-stage status when resuming with PROCEED_BUILD=true."""
    stages = STAGES if copr_repo else [s for s in STAGES if s != "copr"]
    status_label = {"success": "skip", "failed": "retry", None: "run"}
    print("\nPROCEED_BUILD=true — resuming from existing build-report.yaml")
    print(f"  {'package':<30} " + "  ".join(f"{s:<8}" for s in stages))
    print("  " + "-" * (30 + 10 * len(stages)))
    for pkg in packages:
        row = []
        for stage in stages:
            state = (
                build_status.get("stages", {}).get(stage, {}).get(pkg, {}).get("state")
            )
            label = status_label.get(state, state or "run")
            row.append(f"{label:<8}")
        print(f"  {pkg:<30} " + "  ".join(row))
    print()


def load_config() -> tuple[str, str, str, str, str, bool, bool, bool]:
    """Load environment variables.

    Returns (fedora_version, mock_chroot_name, copr_repo, package_filter, skip_filter, skip_mock, skip_copr, synchronous_copr).
    """
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    if fedora_version not in SUPPORTED_FEDORA_VERSIONS:
        sys.exit(
            f"error: unsupported FEDORA_VERSION={fedora_version!r}, "
            f"expected one of {sorted(SUPPORTED_FEDORA_VERSIONS)}"
        )
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    mock_chroot_name = mock_chroot_override or mock_chroot(fedora_version)
    copr_repo = os.environ.get("COPR_REPO", "")
    package_filter = os.environ.get("PACKAGE", "")
    skip_filter = os.environ.get("SKIP_PACKAGES", "")
    skip_mock = os.environ.get("SKIP_MOCK", "").lower() == "true"
    skip_copr = os.environ.get("SKIP_COPR", "").lower() == "true"
    synchronous_copr = os.environ.get("SYNCHRONOUS_COPR_BUILD", "").lower() == "true"
    return (
        fedora_version,
        mock_chroot_name,
        copr_repo,
        package_filter,
        skip_filter,
        skip_mock,
        skip_copr,
        synchronous_copr,
    )


def prepare_packages(package_filter: str, skip_filter: str) -> dict:
    """Load, filter, and expand packages with transitive dependencies."""
    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)
    packages = skip_packages(packages, skip_filter)

    if not package_filter:
        return packages

    graph = build_dep_graph(all_packages)
    expanded: dict = {}
    dep_reason: dict[str, str] = {}
    for name in packages:
        for dep in transitive_deps(name, graph):
            if dep not in expanded:
                expanded[dep] = all_packages[dep]
                dep_reason[dep] = name
        expanded[name] = all_packages[name]

    try:
        order = topological_sort({k: graph[k] & set(expanded) for k in expanded})
    except ValueError as e:
        sys.exit(f"error: {e}")

    requested = {n.strip() for n in package_filter.split(",") if n.strip()}
    print(f"\nPackage build plan ({len(expanded)} total):")
    for pkg in order:
        reason = "" if pkg in requested else f"  (dep of {dep_reason.get(pkg, '?')})"
        print(f"  {pkg}{reason}")

    return {k: expanded[k] for k in order if k in expanded}


def setup_build_status(
    packages: dict, fedora_version: str, mock_chroot_name: str, copr_repo: str
) -> dict:
    """Load/initialize build status and update metadata."""
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    if BUILD_STATUS_YAML.exists():
        build_status = load_build_status()
        if proceed:
            print_proceed_status(packages, build_status, copr_repo)
    else:
        build_status = {"stages": {}}

    build_status.setdefault("run", {})["timestamp"] = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")
    build_status["run"]["fedora_version"] = (
        fedora_version if fedora_version == "rawhide" else int(fedora_version)
    )
    build_status["run"]["mock_chroot"] = mock_chroot_name

    for stage in STAGES:
        build_status.setdefault("stages", {}).setdefault(stage, {})

    save_build_status(build_status)
    return build_status


def run_build_pipeline(
    packages: dict,
    build_status: dict,
    fedora_version: str,
    mock_chroot_name: str,
    copr_repo: str,
    proceed: bool,
    skip_mock: bool = False,
    skip_copr: bool = False,
    synchronous_copr: bool = False,
) -> None:
    """Run per-package pipeline orchestration: validate→spec→vendor→srpm→mock→copr.

    Each package goes through all applicable stages before moving to the next package.
    Per-package skip-on-failure enables faster feedback and independent tracking.
    Tracks rebuilt packages to cascade forced stages to dependents.
    Respects skip_mock and skip_copr flags to skip those stages entirely.
    If synchronous_copr is False (default), COPR builds use --nowait for async submission.
    """
    all_packages = get_packages()

    # Show plan first, before any processing
    _stage["stage-show-plan"].show_plan(copr_repo=copr_repo)
    print("  waiting 5 seconds before proceeding...", flush=True)
    time.sleep(5)

    # Global checks: run once before the per-package loop
    _stage["stage-validate"].run_global_checks(all_packages, build_status)
    save_build_status(build_status)

    if copr_repo:
        _stage["stage-copr"].check_copr_credentials()

    mock_failed: dict[str, bool] = {}
    rebuilt_packages: set[str] = set()

    print("\n=== Full Cycle (Per-Package) ===")
    for pkg, meta in packages.items():
        print(f"\n  {pkg}:")

        # Compute input hashes once per package
        new_hashes = compute_input_hashes(pkg, meta, all_packages)

        # Compute forced stages (from force_run or dependency cascade)
        forced_stages = compute_forced_stages(pkg, meta, build_status, rebuilt_packages)

        # Validate (non-fatal, no caching)
        if not _stage["stage-validate"].run_for_package(
            pkg, meta, all_packages, build_status, fedora_version
        ):
            print(f"    warning: validate failed for {pkg}", file=sys.stderr)
            # non-fatal: continue to spec (matches current behaviour)

        save_build_status(build_status)

        # Spec
        if is_cached("spec", pkg, build_status, new_hashes, forced_stages):
            print("    spec: cached")
            entry = build_status["stages"]["spec"].get(pkg)
            if entry:
                entry["reason"] = "cached"
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_state = (
                build_status.get("stages", {}).get("spec", {}).get(pkg, {}).get("state")
            )
            is_proceed_skip = proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "spec",
                    pkg,
                    build_status,
                    new_hashes,
                    forced_stages,
                    meta,
                    rebuilt_packages,
                )
            )
            if not _stage["stage-spec"].run_for_package(
                pkg, meta, all_packages, build_status, fedora_version
            ):
                inject_stage_meta(
                    "spec",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )
                save_build_status(build_status)
                # Skip downstream stages unless any are forced
                if not any(
                    s in forced_stages for s in ["vendor", "srpm", "mock", "copr"]
                ):
                    continue
            else:
                inject_stage_meta(
                    "spec",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )

        save_build_status(build_status)

        # Vendor
        vendor_entry = build_status.get("stages", {}).get("vendor", {}).get(pkg, {})
        if vendor_entry.get("state") == "skipped" or is_cached(
            "vendor", pkg, build_status, new_hashes, forced_stages
        ):
            print("    vendor: cached")
            if vendor_entry:
                vendor_entry["reason"] = "cached"
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_state = (
                build_status.get("stages", {})
                .get("vendor", {})
                .get(pkg, {})
                .get("state")
            )
            is_proceed_skip = proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "vendor",
                    pkg,
                    build_status,
                    new_hashes,
                    forced_stages,
                    meta,
                    rebuilt_packages,
                )
            )
            result = _stage["stage-vendor"].run_for_package(
                pkg, meta, build_status, fedora_version
            )
            if result is False:
                inject_stage_meta(
                    "vendor",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )
                save_build_status(build_status)
                # Skip downstream stages unless any are forced
                if not any(s in forced_stages for s in ["srpm", "mock", "copr"]):
                    continue
            else:
                inject_stage_meta(
                    "vendor",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )

        save_build_status(build_status)

        # SRPM
        if is_cached("srpm", pkg, build_status, new_hashes, forced_stages):
            print("    srpm: cached")
            entry = build_status["stages"]["srpm"].get(pkg)
            if entry:
                entry["reason"] = "cached"
        else:
            rebuilt_packages.add(pkg)
            started_at = int(time.time())
            prior_state = (
                build_status.get("stages", {}).get("srpm", {}).get(pkg, {}).get("state")
            )
            is_proceed_skip = proceed and prior_state == "success"
            reason = (
                "proceed-skip"
                if is_proceed_skip
                else cache_miss_reason(
                    "srpm",
                    pkg,
                    build_status,
                    new_hashes,
                    forced_stages,
                    meta,
                    rebuilt_packages,
                )
            )
            if not _stage["stage-srpm"].run_for_package(
                pkg, meta, build_status, fedora_version, proceed
            ):
                inject_stage_meta(
                    "srpm",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )
                save_build_status(build_status)
                # Skip downstream stages unless any are forced
                if not any(s in forced_stages for s in ["mock", "copr"]):
                    continue
            else:
                inject_stage_meta(
                    "srpm",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip,
                    reason=reason,
                )

        save_build_status(build_status)

        # Mock
        if skip_mock:
            print("    mock: skipped (SKIP_MOCK=true)")
            entry = build_status["stages"]["mock"].get(pkg)
            if entry:
                entry["reason"] = "SKIP_MOCK"
        else:
            if is_cached("mock", pkg, build_status, new_hashes, forced_stages):
                print("    mock: cached")
                entry = build_status["stages"]["mock"].get(pkg)
                if entry:
                    entry["reason"] = "cached"
            else:
                rebuilt_packages.add(pkg)
                started_at = int(time.time())
                prior_state = (
                    build_status.get("stages", {})
                    .get("mock", {})
                    .get(pkg, {})
                    .get("state")
                )
                is_proceed_skip = proceed and prior_state == "success"
                reason = (
                    "proceed-skip"
                    if is_proceed_skip
                    else cache_miss_reason(
                        "mock",
                        pkg,
                        build_status,
                        new_hashes,
                        forced_stages,
                        meta,
                        rebuilt_packages,
                    )
                )
                if not _stage["stage-mock"].run_for_package(
                    pkg,
                    meta,
                    build_status,
                    fedora_version,
                    mock_chroot_name,
                    proceed,
                    mock_failed,
                    packages,
                ):
                    inject_stage_meta(
                        "mock",
                        pkg,
                        build_status,
                        started_at,
                        new_hashes,
                        update_hashes=not is_proceed_skip,
                        reason=reason,
                    )
                    save_build_status(build_status)
                    # Skip copr unless it is forced
                    if "copr" not in forced_stages:
                        continue
                else:
                    inject_stage_meta(
                        "mock",
                        pkg,
                        build_status,
                        started_at,
                        new_hashes,
                        update_hashes=not is_proceed_skip,
                        reason=reason,
                    )

            save_build_status(build_status)

        # Copr
        if skip_copr:
            print("    copr: skipped (SKIP_COPR=true)")
            entry = build_status["stages"]["copr"].get(pkg)
            if entry:
                entry["reason"] = "SKIP_COPR"
        elif copr_repo:
            if is_cached("copr", pkg, build_status, new_hashes, forced_stages):
                print("    copr: cached")
                entry = build_status["stages"]["copr"].get(pkg)
                if entry:
                    entry["reason"] = "cached"
            else:
                rebuilt_packages.add(pkg)
                started_at = int(time.time())
                prior_state = (
                    build_status.get("stages", {})
                    .get("copr", {})
                    .get(pkg, {})
                    .get("state")
                )
                is_proceed_skip = proceed and prior_state == "success"
                reason = (
                    "proceed-skip"
                    if is_proceed_skip
                    else cache_miss_reason(
                        "copr",
                        pkg,
                        build_status,
                        new_hashes,
                        forced_stages,
                        meta,
                        rebuilt_packages,
                    )
                )
                success = _stage["stage-copr"].run_for_package(
                    pkg,
                    meta,
                    build_status,
                    fedora_version,
                    copr_repo,
                    proceed,
                    synchronous_copr,
                )
                inject_stage_meta(
                    "copr",
                    pkg,
                    build_status,
                    started_at,
                    new_hashes,
                    update_hashes=not is_proceed_skip and success,
                    reason=reason,
                )

            save_build_status(build_status)


def finalize_report(
    packages: dict, build_status: dict, copr_repo: str, synchronous_copr: bool = False
) -> None:
    """Load final status, print summary, write report, and exit if any failed.

    When SYNCHRONOUS_COPR_BUILD=false, 'unknown' states in copr stage are valid (builds pending).
    Only fail if there are actual 'failed' states in non-copr stages or in copr when synchronous.
    """
    final_status = load_build_status()
    final_status["run"] = build_status["run"]
    print_summary(packages, final_status, copr_repo)

    report_path = ROOT / "build-report.yaml"
    report_path.write_text(dump_yaml_pretty(final_status))
    print(f"\nReport written to {report_path.relative_to(ROOT)}")

    any_failed = any(
        info.get("state") == "failed"
        for stage_name, stage_data in final_status.get("stages", {}).items()
        if stage_name not in ("validate", "copr")
        or (stage_name == "copr" and synchronous_copr)
        for info in (stage_data or {}).values()
    )

    # Analyze mock failures if present
    mock_failures = [
        pkg
        for pkg, info in (final_status.get("stages", {}).get("mock", {}) or {}).items()
        if info.get("state") == "failed"
    ]
    if mock_failures:
        report_mock_failures(packages, BUILD_LOG_DIR)

    if any_failed:
        sys.exit(1)


def backup_build_report() -> None:
    """Backup existing build-report.yaml with RFC 3339 timestamp (filesystem-safe)."""
    report_path = ROOT / "build-report.yaml"
    if report_path.exists():
        timestamp = (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace(":", "-")
        )
        backup_path = report_path.parent / f"build-report.{timestamp}.yaml"
        shutil.copy2(report_path, backup_path)
        print(f"Backup created: {backup_path.relative_to(ROOT)}")


def main() -> None:
    (
        fedora_version,
        mock_chroot_name,
        copr_repo,
        package_filter,
        skip_filter,
        skip_mock,
        skip_copr,
        synchronous_copr,
    ) = load_config()

    # Backup existing report before any processing
    backup_build_report()

    packages = prepare_packages(package_filter, skip_filter)
    if not packages:
        sys.exit("error: no packages to build")

    BUILD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    for pkg in packages:
        pkg_log_dir = get_package_log_dir(pkg)
        if pkg_log_dir.exists():
            try:
                shutil.rmtree(pkg_log_dir)
            except OSError as e:
                print(f"warning: could not remove {pkg_log_dir}: {e}", file=sys.stderr)

    build_status = setup_build_status(
        packages, fedora_version, mock_chroot_name, copr_repo
    )

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    run_build_pipeline(
        packages,
        build_status,
        fedora_version,
        mock_chroot_name,
        copr_repo,
        proceed,
        skip_mock,
        skip_copr,
        synchronous_copr,
    )
    finalize_report(packages, build_status, copr_repo, synchronous_copr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
