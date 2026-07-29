#!/usr/bin/env python3
"""Stage 3: Build packages with mock, manage local-repo for dep resolution.

Reads packages.yaml and build-report.yaml for srpm stage results.
Skips packages where srpm stage failed or a local build-dep failed.
Records build results and mock log paths in build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  PROCEED_BUILD   Skip packages where mock stage already succeeded
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import re
import shutil
import subprocess
import sys
from functools import cmp_to_key
from pathlib import Path
from typing import Any

from lib.config import setup_logging
from lib.deps import build_dep_graph, effective_deps, topological_sort
from lib.paths import LOCAL_REPO, ROOT, get_package_log_dir, mock_chroot
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    init_stage,
    now_epoch,
    save_build_status,
)


def failed_local_dep(
    name: str, meta: dict, all_packages: dict, failed: dict
) -> str | None:
    for dep in effective_deps(name, meta, all_packages):
        if failed.get(dep):
            return dep
    return None


def regenerate_repo_metadata() -> None:
    """Regenerate local repo metadata to index all packages."""
    result = subprocess.run(
        ["createrepo_c", "--update", str(LOCAL_REPO)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        logging.error(
            "createrepo_c failed: %s",
            result.stderr.decode() if result.stderr else "",
        )
        raise RuntimeError(f"createrepo_c failed with code {result.returncode}")


def _rpm_query(rpm_path: Path, fmt: str) -> str:
    """Query a single field from an RPM file via rpm --queryformat."""
    result = subprocess.run(
        ["rpm", "-qp", "--queryformat", fmt, str(rpm_path)],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _evr(rpm_path: Path) -> str:
    """Return epoch:version-release for an RPM, normalizing unset epoch to 0."""
    epoch = _rpm_query(rpm_path, "%|EPOCH?{%{EPOCH}}:{0}|")
    version_release = _rpm_query(rpm_path, "%{VERSION}-%{RELEASE}")
    return f"{epoch}:{version_release}"


def _vercmp(evr_a: str, evr_b: str) -> int:
    """Compare two epoch:version-release strings via rpmdev-vercmp.

    Returns -1, 0, or 1 (evr_a older/equal/newer than evr_b).
    """
    result = subprocess.run(
        ["rpmdev-vercmp", evr_a, evr_b],
        capture_output=True,
        text=True,
    )
    if result.returncode == 11:
        return 1
    if result.returncode == 12:
        return -1
    return 0


def prune_local_repo() -> bool:
    """Delete all but the newest NVR per (name, arch) in LOCAL_REPO.

    Nothing else here ever removes an old build: every rebuild only adds a
    new NVR, so a stale hyprutils-0.13.1 can sit next to 0.14.0 forever (see
    docs/bugs.md). mock's dnf resolves build deps against everything in the
    repo, so this only bloats disk today, but a repo left in a half-pruned
    state after a partial run is exactly the kind of thing that could
    resolve the wrong version later.

    Returns True if anything was removed.
    """
    by_key: dict[tuple[str, str], list[tuple[str, Path]]] = {}
    for rpm_path in LOCAL_REPO.glob("*.rpm"):
        if rpm_path.name.endswith(".src.rpm"):
            continue
        name = _rpm_query(rpm_path, "%{NAME}")
        arch = _rpm_query(rpm_path, "%{ARCH}")
        if not name or not arch:
            continue
        by_key.setdefault((name, arch), []).append((_evr(rpm_path), rpm_path))

    def _by_evr(a: tuple[str, Path], b: tuple[str, Path]) -> int:
        return _vercmp(a[0], b[0])

    removed = False
    for entries in by_key.values():
        if len(entries) < 2:
            continue
        entries.sort(key=cmp_to_key(_by_evr))
        for _stale_evr, stale_path in entries[:-1]:
            stale_path.unlink()
            removed = True
    return removed


def update_local_repo(mock_chroot: str) -> None:
    result_dir = Path("/var/lib/mock") / mock_chroot / "result"
    LOCAL_REPO.mkdir(exist_ok=True)
    copied = False
    for rpm in result_dir.glob("*.rpm"):
        if not rpm.name.endswith(".src.rpm"):
            shutil.copy2(rpm, LOCAL_REPO)
            copied = True
    pruned = prune_local_repo()
    if copied or pruned:
        regenerate_repo_metadata()


def copy_mock_results(mock_chroot: str, pkg: str) -> list[str]:
    result_dir = Path("/var/lib/mock") / mock_chroot / "result"
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("build.log", "root.log", "state.log"):
        dst = pkg_log_dir / f"21-mock-{name}"
        try:
            shutil.copy2(result_dir / name, dst)
            copied.append(str(dst.relative_to(ROOT)))
        except (FileNotFoundError, PermissionError):
            pass
    return copied


def run_for_package(
    pkg: str,
    meta: dict,
    build_status: dict,
    fedora_version: str,
    mock_chroot_name: str,
    proceed: bool,
    failed: dict,
    all_packages: dict,
) -> bool:
    """Run mock build for a single package. Return True on success/skip, False on failure.

    Updates build_status["stages"]["mock"][pkg] in-place.
    Updates failed[pkg] to indicate if this package failed.
    Does not call save_build_status().
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_status["stages"]["mock"][pkg] = {
            "state": "skipped",
            "version": None,
            "log": None,
            "force_run": False,
            "reason": "config: skip",
        }
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    has_devel = "devel" in meta
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "20-mock.log"
    log.unlink(missing_ok=True)

    # Skip if mock stage already succeeded
    mock_state = (
        build_status.get("stages", {}).get("mock", {}).get(pkg, {}).get("state")
    )
    if proceed and verbose_proceed_check("mock", pkg, mock_state):
        status("mock", pkg, "skip", "already succeeded")
        return True  # preserve existing entry (has completed_at from prior run)

    blocker = failed_local_dep(pkg, meta, all_packages, failed)
    srpm_stage = build_status.get("stages", {}).get("srpm", {})
    srpm_state = srpm_stage.get(pkg, {}).get("state", "")
    srpm_path = srpm_stage.get(pkg, {}).get("path")

    if srpm_state in ("failed", "skipped") or blocker or not srpm_path:
        detail = (
            f"local dep failed: {blocker}"
            if blocker and srpm_state not in ("failed", "skipped")
            else f"srpm {srpm_state}"
        )
        failed[pkg] = True
        status("mock", pkg, "skip", detail)
        entry: dict[str, Any] = {
            "state": "skipped",
            "version": ver,
            "log": None,
            "force_run": False,
            "reason": detail,
        }
        if has_devel:
            entry["subpackages"] = {"devel": {"state": "skipped", "version": ver}}
        build_status["stages"]["mock"][pkg] = entry
        return True

    cmd = ["mock", "-r", mock_chroot_name, "--rebuild", srpm_path]
    if (LOCAL_REPO / "repodata").exists():
        cmd.insert(3, "--addrepo")
        cmd.insert(4, f"file://{LOCAL_REPO}")
    print(f"  [RUN]  mock: {pkg}", flush=True)
    ok, _, _ = run_cmd(cmd, log)
    mock_logs = copy_mock_results(mock_chroot_name, pkg)
    state = "success" if ok else "failed"
    if not ok:
        failed[pkg] = True
    else:
        failed[pkg] = False
        update_local_repo(mock_chroot_name)
    status("mock", pkg, "ok" if ok else "fail")

    entry = {
        "state": state,
        "version": ver,
        "log": str(log.relative_to(ROOT)),
        "force_run": False,
        **({"completed_at": now_epoch()} if ok else {}),
    }
    if mock_logs:
        entry["mock_logs"] = mock_logs
    if has_devel:
        entry["subpackages"] = {"devel": {"state": state, "version": ver}}
    build_status["stages"]["mock"][pkg] = entry

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    mock_chroot_name = mock_chroot_override or mock_chroot(fedora_version)
    if not re.match(r"^[\w.-]+$", mock_chroot_name):
        raise ValueError(f"Invalid MOCK_CHROOT: {mock_chroot_name}")

    packages, build_status = init_stage("mock")

    # Regenerate repo metadata before building to ensure fresh package index
    regenerate_repo_metadata()

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    failed: dict[str, bool] = {}

    # Sort packages by dependency order (dependencies first)
    dep_graph = build_dep_graph(packages)
    build_order = topological_sort(dep_graph)

    failed_overall = False
    print("\n=== mock ===")
    for pkg in build_order:
        meta = packages[pkg]
        if not run_for_package(
            pkg,
            meta,
            build_status,
            fedora_version,
            mock_chroot_name,
            proceed,
            failed,
            packages,
        ):
            failed_overall = True
        save_build_status(build_status)

    if failed_overall:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
