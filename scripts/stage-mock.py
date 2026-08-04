#!/usr/bin/env python3
"""Stage 3: Build packages with mock, manage local-repo for dep resolution.

Reads packages.yaml and build-report.db for srpm stage results.
Skips packages where srpm stage failed or a local build-dep failed.
Records build results and mock log paths in build-report.db.

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

from lib import build_db
from lib.config import setup_logging
from lib.deps import build_dep_graph, effective_deps, topological_sort
from lib.paths import (
    ARCH,
    DISTRO,
    LOCAL_REPO,
    ROOT,
    get_package_log_dir,
    resolve_target,
)
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import apply_os_overrides, prepare_stage


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

    Also drops the artifact ledger row for anything unlinked, so `db-usage`
    never reports a file that prune already removed.

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
            build_db.delete_artifact("repo", str(stale_path))
            removed = True
    return removed


def update_local_repo(mock_chroot: str) -> list[str]:
    """Copy this build's RPMs (excluding .src.rpm) from mock's result dir into
    LOCAL_REPO, prune stale NVRs, and regenerate repo metadata if anything
    changed. Returns the absolute paths of the RPMs copied.
    """
    result_dir = Path("/var/lib/mock") / mock_chroot / "result"
    LOCAL_REPO.mkdir(exist_ok=True)
    copied: list[str] = []
    for rpm in result_dir.glob("*.rpm"):
        if not rpm.name.endswith(".src.rpm"):
            dest = LOCAL_REPO / rpm.name
            shutil.copy2(rpm, dest)
            copied.append(str(dest))
    pruned = prune_local_repo()
    if copied or pruned:
        regenerate_repo_metadata()
    return copied


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
    fedora_version: str,
    target: str,
    proceed: bool,
    failed: dict,
    all_packages: dict,
    run_id: int,
) -> bool:
    """Run mock build for a single package. Return True on success/skip, False on failure.

    Writes the mock stage row for `pkg` and updates failed[pkg] to indicate
    if this package failed.
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_db.set_stage(
            pkg, "mock", target, run_id, "skipped", reason="config: skip"
        )
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    has_devel = 1 if "devel" in meta else 0
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "20-mock.log"
    log.unlink(missing_ok=True)

    # Skip if mock stage already succeeded
    mock_entry = build_db.get_stage(pkg, "mock", target)
    mock_state = mock_entry.get("state") if mock_entry else None
    if proceed and verbose_proceed_check("mock", pkg, mock_state):
        status("mock", pkg, "skip", "already succeeded")
        return True  # preserve existing entry (has completed_at from prior run)

    blocker = failed_local_dep(pkg, meta, all_packages, failed)
    srpm_entry = build_db.get_stage(pkg, "srpm", target)
    srpm_state = srpm_entry.get("state", "") if srpm_entry else ""
    srpm_path = srpm_entry.get("path") if srpm_entry else None
    # A "success" srpm row whose recorded file has since vanished (e.g. a pruned
    # rpmbuild-volume) must not be handed to `mock --rebuild` -- see docs/bugs.md
    # BUG-0015, the exact "Cannot find/open srpm" failure this guards against.
    srpm_missing = bool(srpm_path) and not Path(str(srpm_path)).exists()

    if srpm_state in ("failed", "skipped") or blocker or not srpm_path or srpm_missing:
        detail = (
            f"local dep failed: {blocker}"
            if blocker and srpm_state not in ("failed", "skipped")
            else "srpm artifact missing"
            if srpm_missing
            else f"srpm {srpm_state}"
        )
        failed[pkg] = True
        status("mock", pkg, "skip", detail)
        build_db.set_stage(
            pkg,
            "mock",
            target,
            run_id,
            "skipped",
            version=ver,
            reason=detail,
            has_devel=has_devel,
        )
        return True

    # rpmbuild_networking/use_host_resolv off: reproduce COPR's offline %build
    # step locally (docs/todo.md TODO-0004), so an incomplete vendor tree fails
    # here instead of only on COPR. Dep resolution (dnf install of BuildRequires)
    # happens before %build and is unaffected -- it uses --addrepo below plus
    # the chroot's configured Fedora repos, not this networking flag.
    cmd = [
        "mock",
        "-r",
        target,
        "--config-opts",
        "rpmbuild_networking=False",
        "--config-opts",
        "use_host_resolv=False",
    ]
    if (LOCAL_REPO / "repodata").exists():
        cmd += ["--addrepo", f"file://{LOCAL_REPO}"]
    cmd += ["--rebuild", srpm_path]
    print(f"  [RUN]  mock: {pkg}", flush=True)
    ok, _, _ = run_cmd(cmd, log)
    # Copies build.log/root.log/state.log to logs/build/<pkg>/, then records
    # each as an artifact (repo-relative path, matching the `log` column
    # convention used everywhere else in this file).
    for mock_log in copy_mock_results(target, pkg):
        build_db.record_artifact(mock_log, "repo", "mock_log", pkg, target, ver)
    state = "success" if ok else "failed"
    if not ok:
        failed[pkg] = True
    else:
        failed[pkg] = False
        # Copied RPMs get absolute paths (unlike mock_log above): LOCAL_REPO
        # isn't always under ROOT in tests, and this stays correct either way.
        for rpm_path in update_local_repo(target):
            build_db.record_artifact(rpm_path, "repo", "rpm", pkg, target, ver)
    status("mock", pkg, "ok" if ok else "fail")

    extra: dict[str, Any] = {}
    if ok:
        extra["completed_at"] = build_db.now_epoch()
    build_db.set_stage(
        pkg,
        "mock",
        target,
        run_id,
        state,
        version=ver,
        log=str(log.relative_to(ROOT)),
        has_devel=has_devel,
        **extra,
    )

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)
    if not re.match(r"^[\w.-]+$", target):
        raise ValueError(f"Invalid MOCK_CHROOT: {target}")

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    run_id = build_db.start_run(
        target,
        DISTRO,
        fedora_version,
        ARCH,
        package_filter=os.environ.get("PACKAGE", ""),
    )

    packages = prepare_stage("mock", target, proceed)

    # Regenerate repo metadata before building to ensure fresh package index
    regenerate_repo_metadata()

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
            fedora_version,
            target,
            proceed,
            failed,
            packages,
            run_id,
        ):
            failed_overall = True

    build_db.finish_run(run_id, "failed" if failed_overall else "ok")
    if failed_overall:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
