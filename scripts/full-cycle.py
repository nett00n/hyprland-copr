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
  PROCEED_BUILD   If 'true', skip stages already succeeded; preserve build-report.yaml
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib.deps import build_dep_graph, topological_sort, transitive_deps
from lib.log_analysis import report_mock_failures, report_srpm_failures
from lib.paths import LOG_DIR, ROOT
from lib.reporting import print_summary
from lib.yaml_utils import (
    BUILD_STATUS_YAML,
    STAGES,
    filter_packages,
    get_packages,
    load_build_status,
    save_build_status,
)

PYTHON = sys.executable
SCRIPTS = ROOT / "scripts"


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
    mock_chroot = os.environ.get(
        "MOCK_CHROOT",
        "fedora-rawhide-x86_64"
        if fedora_version == "rawhide"
        else f"fedora-{fedora_version}-x86_64",
    )
    copr_repo = os.environ.get("COPR_REPO", "")
    package_filter = os.environ.get("PACKAGE", "")

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)

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

    LOG_DIR.mkdir(exist_ok=True)
    # Clean old logs for selected packages
    for pkg in packages:
        for old_log in [*LOG_DIR.glob(f"*-{pkg}.log"), *LOG_DIR.glob(f"*-{pkg}-*.log")]:
            old_log.unlink()

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
    build_status["run"]["mock_chroot"] = mock_chroot

    # Ensure all stage keys exist
    for stage in STAGES:
        build_status.setdefault("stages", {}).setdefault(stage, {})

    save_build_status(build_status)

    stage_env = {
        "FEDORA_VERSION": fedora_version,
        "MOCK_CHROOT": mock_chroot,
        "PACKAGE": ",".join(packages.keys()) if package_filter else "",
        "COPR_REPO": copr_repo,
        "PROCEED_BUILD": "true" if proceed else "",
    }

    run_stage(SCRIPTS / "stage-validate.py", stage_env)
    run_stage(SCRIPTS / "stage-spec.py", stage_env)
    run_stage(SCRIPTS / "stage-vendor.py", stage_env)
    srpm_ok = run_stage(SCRIPTS / "stage-srpm.py", stage_env)
    if not srpm_ok:
        report_srpm_failures(packages, LOG_DIR)
    mock_ok = run_stage(SCRIPTS / "stage-mock.py", stage_env)
    if not mock_ok:
        report_mock_failures(packages, LOG_DIR)
    if copr_repo:
        run_stage(SCRIPTS / "stage-copr.py", stage_env)

    # Load final status and print summary
    final_status = load_build_status()
    # Merge run metadata back
    final_status["run"] = build_status["run"]
    print_summary(packages, final_status, copr_repo)

    # Write build-report.yaml (compatible with gen-report.py)
    report_path = ROOT / "build-report.yaml"
    report_path.write_text(
        yaml.dump(
            final_status, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
    )
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
