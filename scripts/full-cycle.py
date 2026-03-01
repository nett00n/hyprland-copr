#!/usr/bin/env python3
"""Full build cycle orchestrator with YAML report generation.

Must be run inside the rpm toolbox container (invoked via Makefile).

Runs: spec generation → srpm (sources + rpmbuild -bs) → mock → copr
Writes build-report.yaml and per-stage logs under logs/ in the repo root.

Environment variables:
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO       Copr repo slug, e.g. nett00n/hyprland (optional)
  PACKAGE         Build only this package (optional, comma-separated)
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_YAML = ROOT / "packages.yaml"
PYTHON = sys.executable
LOG_DIR = ROOT / "logs"
LOCAL_REPO = ROOT / "local-repo"

STAGES = ["spec", "srpm", "mock", "copr"]


def run(cmd: str, log_path: Path | None = None) -> tuple[bool, str, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if log_path:
        with open(log_path, "a") as fh:
            fh.write(f"$ {cmd}\n")
            if result.stdout:
                fh.write(result.stdout)
            if result.stderr:
                fh.write(result.stderr)
            fh.write(f"[exit: {result.returncode}]\n\n")
    return result.returncode == 0, result.stdout, result.stderr


def status(stage: str, pkg: str, result: str) -> None:
    tag = {"ok": "[OK]  ", "fail": "[FAIL]", "skip": "[SKIP]"}[result]
    print(f"  {tag} {stage}: {pkg}")


def nvr(version: str, release: int | str, fedora_version: str) -> str:
    dist = "rawhide" if fedora_version == "rawhide" else f"fc{fedora_version}"
    return f"{version}-{release}.{dist}"


def pkg_stage(state: str, version_str: str, **extra) -> dict:
    return {"state": state, "version": version_str, **extra}


def with_devel(entry: dict, has_devel: bool, state: str, ver: str) -> dict:
    if has_devel:
        entry["subpackages"] = {"devel": pkg_stage(state, ver)}
    return entry


def log_rel(log_path: Path) -> str:
    return str(log_path.relative_to(ROOT))


def find_srpm(pkg: str) -> str | None:
    srpm_dir = Path.home() / "rpmbuild" / "SRPMS"
    matches = sorted(
        srpm_dir.glob(f"{pkg}-*.src.rpm"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return str(matches[0]) if matches else None


def parse_build_id(output: str) -> int | None:
    for line in output.splitlines():
        if "Created builds:" in line:
            try:
                return int(line.split()[-1])
            except (ValueError, IndexError):
                pass
    return None


def failed_local_dep(meta: dict, all_packages: dict, failed: dict) -> str | None:
    for dep in meta.get("build_requires", []):
        base = dep.removesuffix("-devel")
        if base in all_packages and failed.get(base):
            return base
    return None


def update_local_repo(mock_chroot: str) -> None:
    result_dir = Path("/var/lib/mock") / mock_chroot / "result"
    LOCAL_REPO.mkdir(exist_ok=True)
    copied = False
    for rpm in result_dir.glob("*.rpm"):
        if not rpm.name.endswith(".src.rpm"):
            shutil.copy2(rpm, LOCAL_REPO)
            copied = True
    if copied or not (LOCAL_REPO / "repodata").exists():
        subprocess.run(
            ["createrepo_c", "--update", str(LOCAL_REPO)], capture_output=True
        )


def copy_mock_results(mock_chroot: str, pkg: str) -> list[str]:
    result_dir = Path("/var/lib/mock") / mock_chroot / "result"
    copied: list[str] = []
    for name in ("build.log", "root.log", "state.log"):
        dst = LOG_DIR / f"{pkg}-21-mock-{name}"
        try:
            shutil.copy2(result_dir / name, dst)
            copied.append(log_rel(dst))
        except (FileNotFoundError, PermissionError):
            pass
    return copied


def print_summary(packages: dict, report: dict, copr_repo: str) -> None:
    stage_keys = ["spec", "srpm", "mock"] + (["copr"] if copr_repo else [])
    col_w = max(len(p) for p in packages) + 2
    header = f"{'package':<{col_w}}" + "".join(f"{s:<10}" for s in stage_keys)
    sep = "-" * len(header)
    print(f"\nSummary:\n{sep}\n{header}\n{sep}")
    for pkg in packages:
        row = f"{pkg:<{col_w}}"
        for stage in stage_keys:
            state = report["stages"][stage].get(pkg, {}).get("state", "-")
            icon = {"success": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(
                state, state
            )
            row += f"{icon:<10}"
        print(row)
    print(sep)


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

    all_packages: dict[str, Any] = yaml.safe_load(PACKAGES_YAML.read_text())["packages"]

    if package_filter:
        names = [n.strip() for n in package_filter.split(",") if n.strip()]
        unknown = [n for n in names if n not in all_packages]
        if unknown:
            sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
        packages = {n: all_packages[n] for n in names}
    else:
        packages = all_packages

    LOG_DIR.mkdir(exist_ok=True)

    for pkg in packages:
        for old_log in [*LOG_DIR.glob(f"*-{pkg}.log"), *LOG_DIR.glob(f"*-{pkg}-*.log")]:
            old_log.unlink()

    report: dict[str, Any] = {
        "run": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fedora_version": fedora_version
            if fedora_version == "rawhide"
            else int(fedora_version),
            "mock_chroot": mock_chroot,
        },
        "stages": {s: {} for s in STAGES},
    }

    # pre-compute per-package constants used across all stages
    vers = {
        pkg: nvr(meta["version"], meta.get("release", 1), fedora_version)
        for pkg, meta in packages.items()
    }
    has_devels = {pkg: "devel" in meta for pkg, meta in packages.items()}

    failed: dict[str, bool] = dict.fromkeys(packages, False)
    srpm_paths: dict[str, str | None] = {}

    # ── spec ────────────────────────────────────────────────────────────────
    print("\n=== spec ===")
    for pkg, meta in packages.items():
        ver, has_devel = vers[pkg], has_devels[pkg]
        log = LOG_DIR / f"{pkg}-00-spec.log"
        ok, _, _ = run(f"{PYTHON} {ROOT}/scripts/gen-spec.py {pkg}", log)
        state = "success" if ok else "failed"
        if not ok:
            failed[pkg] = True
        status("spec", pkg, "ok" if ok else "fail")
        report["stages"]["spec"][pkg] = with_devel(
            pkg_stage(state, ver, log=log_rel(log)), has_devel, state, ver
        )

    # ── srpm (sources + rpmbuild -bs) ────────────────────────────────────────
    print("\n=== srpm ===")
    for pkg, meta in packages.items():
        ver, has_devel = vers[pkg], has_devels[pkg]
        spec = f"{ROOT}/packages/{pkg}/{pkg}.spec"
        log = LOG_DIR / f"{pkg}-10-srpm.log"

        if failed[pkg]:
            status("srpm", pkg, "skip")
            report["stages"]["srpm"][pkg] = with_devel(
                pkg_stage("skipped", ver, path=None, log=None),
                has_devel,
                "skipped",
                ver,
            )
            continue

        ok, _, _ = run(f"spectool -g -R {spec}", log)
        if not ok:
            failed[pkg] = True
            status("srpm", pkg, "fail")
            report["stages"]["srpm"][pkg] = with_devel(
                pkg_stage("failed", ver, path=None, log=log_rel(log)),
                has_devel,
                "failed",
                ver,
            )
            continue

        ok, _, _ = run(f"rpmbuild -bs {spec}", log)
        if not ok:
            failed[pkg] = True
            status("srpm", pkg, "fail")
            report["stages"]["srpm"][pkg] = with_devel(
                pkg_stage("failed", ver, path=None, log=log_rel(log)),
                has_devel,
                "failed",
                ver,
            )
            continue

        path = find_srpm(pkg)
        srpm_paths[pkg] = path
        status("srpm", pkg, "ok")
        report["stages"]["srpm"][pkg] = with_devel(
            pkg_stage("success", ver, path=path, log=log_rel(log)),
            has_devel,
            "success",
            ver,
        )

    # ── mock ────────────────────────────────────────────────────────────────
    print("\n=== mock ===")
    for pkg, meta in packages.items():
        ver, has_devel = vers[pkg], has_devels[pkg]
        log = LOG_DIR / f"{pkg}-20-mock.log"

        blocker = failed_local_dep(meta, packages, failed)
        if failed[pkg] or blocker:
            if blocker and not failed[pkg]:
                print(f"  [SKIP] mock: {pkg} — local dep failed: {blocker}")
                failed[pkg] = True
            status("mock", pkg, "skip")
            report["stages"]["mock"][pkg] = with_devel(
                pkg_stage("skipped", ver, log=None), has_devel, "skipped", ver
            )
            continue

        srpm = srpm_paths.get(pkg)
        if not srpm:
            failed[pkg] = True
            status("mock", pkg, "fail")
            report["stages"]["mock"][pkg] = with_devel(
                pkg_stage("failed", ver, log=log_rel(log)), has_devel, "failed", ver
            )
            continue

        addrepo = (
            f"--addrepo file://{LOCAL_REPO}"
            if (LOCAL_REPO / "repodata").exists()
            else ""
        )
        ok, _, _ = run(f"mock -r {mock_chroot} {addrepo} --rebuild {srpm}".strip(), log)
        mock_logs = copy_mock_results(mock_chroot, pkg)
        state = "success" if ok else "failed"
        if not ok:
            failed[pkg] = True
        else:
            update_local_repo(mock_chroot)
        status("mock", pkg, "ok" if ok else "fail")
        entry = pkg_stage(state, ver, log=log_rel(log))
        if mock_logs:
            entry["mock_logs"] = mock_logs
        report["stages"]["mock"][pkg] = with_devel(entry, has_devel, state, ver)

    # ── copr ────────────────────────────────────────────────────────────────
    print("\n=== copr ===")
    for pkg, meta in packages.items():
        ver, has_devel = vers[pkg], has_devels[pkg]
        log = LOG_DIR / f"{pkg}-30-copr.log"

        if not copr_repo or failed[pkg]:
            status("copr", pkg, "skip")
            report["stages"]["copr"][pkg] = with_devel(
                pkg_stage("skipped", ver, build_id=None, log=None),
                has_devel,
                "skipped",
                ver,
            )
            continue

        srpm = srpm_paths.get(pkg)
        ok, stdout, _ = run(f"copr-cli build {copr_repo} {srpm}", log)
        state = "success" if ok else "failed"
        if not ok:
            failed[pkg] = True
        build_id = parse_build_id(stdout) if ok else None
        status("copr", pkg, "ok" if ok else "fail")
        report["stages"]["copr"][pkg] = with_devel(
            pkg_stage(state, ver, build_id=build_id, log=log_rel(log)),
            has_devel,
            state,
            ver,
        )

    # ── summary + report ─────────────────────────────────────────────────────
    print_summary(packages, report, copr_repo)

    report_path = ROOT / "build-report.yaml"
    report_path.write_text(
        yaml.dump(report, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )
    print(f"\nReport written to {report_path.relative_to(ROOT)}")

    if any(failed.values()):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
