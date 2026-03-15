#!/usr/bin/env python3
"""Full build cycle orchestrator: spec → srpm → mock → copr.

Delegates each stage to the appropriate stage-*.py script, then
prints a summary table and writes build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO       Copr repo slug, e.g. nett00n/hyprland (optional)
  PACKAGE         Build only this package (optional, comma-separated)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  PROCEED_BUILD   If 'true', skip stages already succeeded; preserve build-report.yaml
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.deps import build_dep_graph, topological_sort, transitive_deps
from lib.log_analysis import report_mock_failures, report_srpm_failures
from lib.paths import BUILD_LOG_DIR, ROOT, SOURCES_DIR, get_package_log_dir, mock_chroot
from lib.reporting import print_summary
from lib.vendor import is_go_package, vendor_tarball_path
from lib.yaml_utils import (
    BUILD_STATUS_YAML,
    STAGES,
    dump_yaml_pretty,
    filter_packages,
    get_packages,
    load_build_status,
    save_build_status,
    skip_packages,
)

PYTHON = sys.executable
SCRIPTS = ROOT / "scripts"


def needs_vendoring(packages: dict, fedora_version: str) -> bool:
    """Check if any Go package needs vendoring (vendor tarball missing)."""
    for pkg, meta in packages.items():
        if not is_go_package(meta):
            continue
        version = str(meta.get("version", ""))
        tarball = vendor_tarball_path(pkg, version, SOURCES_DIR)
        if not tarball.exists():
            return True
    return False


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


def run_stage(script: Path, env: dict) -> bool:
    """Run a stage script, returning True if it succeeded (exit 0)."""
    result = subprocess.run(
        [PYTHON, str(script)],
        env={**os.environ, **env},
    )
    return result.returncode == 0


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    mock_chroot_name = mock_chroot_override or mock_chroot(fedora_version)
    copr_repo = os.environ.get("COPR_REPO", "")
    package_filter = os.environ.get("PACKAGE", "")
    skip_filter = os.environ.get("SKIP_PACKAGES", "")

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)
    packages = skip_packages(packages, skip_filter)

    # Expand selected packages to include transitive deps, then sort topologically
    if package_filter:
        graph = build_dep_graph(all_packages)
        expanded: dict = {}
        dep_reason: dict[str, str] = {}  # dep -> "pulled in by <name>"
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
        packages = {k: expanded[k] for k in order if k in expanded}

        requested = {n.strip() for n in package_filter.split(",") if n.strip()}
        print(f"\nPackage build plan ({len(packages)} total):")
        for pkg in order:
            if pkg not in expanded:
                continue
            reason = (
                "" if pkg in requested else f"  (dep of {dep_reason.get(pkg, '?')})"
            )
            print(f"  {pkg}{reason}")

    BUILD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Clean old logs for selected packages
    for pkg in packages:
        pkg_log_dir = get_package_log_dir(pkg)
        if pkg_log_dir.exists():
            shutil.rmtree(pkg_log_dir)

    # Load or initialize build status; preserve previous results
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    if BUILD_STATUS_YAML.exists():
        build_status = load_build_status()
        if proceed:
            print_proceed_status(packages, build_status, copr_repo)
    else:
        build_status = {"stages": {}}

    # Update run metadata
    build_status.setdefault("run", {})["timestamp"] = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")
    build_status["run"]["fedora_version"] = (
        fedora_version if fedora_version == "rawhide" else int(fedora_version)
    )
    build_status["run"]["mock_chroot"] = mock_chroot_name

    # Ensure all stage keys exist
    for stage in STAGES:
        build_status.setdefault("stages", {}).setdefault(stage, {})

    save_build_status(build_status)

    stage_env = {
        "FEDORA_VERSION": fedora_version,
        "MOCK_CHROOT": mock_chroot_name,
        "PACKAGE": ",".join(packages.keys()) if package_filter else "",
        "COPR_REPO": copr_repo,
        "PROCEED_BUILD": "true" if proceed else "",
    }

    run_stage(SCRIPTS / "stage-validate.py", stage_env)
    run_stage(SCRIPTS / "stage-spec.py", stage_env)
    if needs_vendoring(packages, fedora_version):
        run_stage(SCRIPTS / "stage-vendor.py", stage_env)
    srpm_ok = run_stage(SCRIPTS / "stage-srpm.py", stage_env)
    if not srpm_ok:
        report_srpm_failures(packages, BUILD_LOG_DIR)
    mock_ok = run_stage(SCRIPTS / "stage-mock.py", stage_env)
    if not mock_ok:
        report_mock_failures(packages, BUILD_LOG_DIR)
    if copr_repo:
        run_stage(SCRIPTS / "stage-copr.py", stage_env)

    # Load final status and print summary
    final_status = load_build_status()
    # Merge run metadata back
    final_status["run"] = build_status["run"]
    print_summary(packages, final_status, copr_repo)

    # Write build-report.yaml (compatible with gen-report.py)
    report_path = ROOT / "build-report.yaml"
    report_path.write_text(dump_yaml_pretty(final_status))
    print(f"\nReport written to {report_path.relative_to(ROOT)}")

    any_failed = any(
        info.get("state") == "failed"
        for stage_data in final_status.get("stages", {}).values()
        for info in (stage_data or {}).values()
    )
    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
