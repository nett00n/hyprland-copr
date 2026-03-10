#!/usr/bin/env python3
"""Stage 3: Build packages with mock, manage local-repo for dep resolution.

Reads packages.yaml and logs/build-status.yaml for srpm stage results.
Skips packages where srpm stage failed or a local build-dep failed.
Records build results and mock log paths in build-status.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  PROCEED_BUILD   Skip packages where mock stage already succeeded
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from lib.deps import infer_deps
from lib.paths import LOCAL_REPO, LOG_DIR, ROOT
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    filter_packages,
    get_packages,
    load_build_status,
    now_epoch,
    save_build_status,
)


def failed_local_dep(
    name: str, meta: dict, all_packages: dict, failed: dict
) -> str | None:
    for dep in infer_deps(name, meta, all_packages):
        if failed.get(dep):
            return dep
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
            copied.append(str(dst.relative_to(ROOT)))
        except (FileNotFoundError, PermissionError):
            pass
    return copied


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot = os.environ.get(
        "MOCK_CHROOT",
        "fedora-rawhide-x86_64"
        if fedora_version == "rawhide"
        else f"fedora-{fedora_version}-x86_64",
    )
    if not re.match(r"^[\w.-]+$", mock_chroot):
        raise ValueError(f"Invalid MOCK_CHROOT: {mock_chroot}")
    package_filter = os.environ.get("PACKAGE", "")

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)

    LOG_DIR.mkdir(exist_ok=True)
    build_status = load_build_status()
    srpm_stage = build_status.get("stages", {}).get("srpm", {})

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    stages = build_status.setdefault("stages", {})
    if not proceed:
        stages["mock"] = {}
    stages.setdefault("mock", {})

    failed: dict[str, bool] = {}

    failed_overall = False
    print("\n=== mock ===")
    for pkg, meta in packages.items():
        meta = apply_os_overrides(meta, fedora_version)
        if meta.get("_skip"):
            print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
            build_status["stages"]["mock"][pkg] = {
                "state": "skipped",
                "version": None,
                "log": None,
            }
            continue
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        has_devel = "devel" in meta
        log = LOG_DIR / f"{pkg}-20-mock.log"
        log.unlink(missing_ok=True)

        # Skip if mock stage already succeeded
        mock_state = (
            build_status.get("stages", {}).get("mock", {}).get(pkg, {}).get("state")
        )
        if proceed and verbose_proceed_check("mock", pkg, mock_state):
            status("mock", pkg, "skip", "already succeeded")
            continue  # preserve existing entry (has completed_at from prior run)

        blocker = failed_local_dep(pkg, meta, packages, failed)
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
            entry: dict[str, Any] = {"state": "skipped", "version": ver, "log": None}
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "skipped", "version": ver}}
            build_status["stages"]["mock"][pkg] = entry
            continue

        cmd = ["mock", "-r", mock_chroot, "--rebuild", srpm_path]
        if (LOCAL_REPO / "repodata").exists():
            cmd.insert(3, "--addrepo")
            cmd.insert(4, f"file://{LOCAL_REPO}")
        ok, _, _ = run_cmd(cmd, log)
        mock_logs = copy_mock_results(mock_chroot, pkg)
        state = "success" if ok else "failed"
        if not ok:
            failed[pkg] = True
            failed_overall = True
        else:
            failed[pkg] = False
            update_local_repo(mock_chroot)
        status("mock", pkg, "ok" if ok else "fail")

        entry = {
            "state": state,
            "version": ver,
            "log": str(log.relative_to(ROOT)),
            **({"completed_at": now_epoch()} if ok else {}),
        }
        if mock_logs:
            entry["mock_logs"] = mock_logs
        if has_devel:
            entry["subpackages"] = {"devel": {"state": state, "version": ver}}
        build_status["stages"]["mock"][pkg] = entry
        save_build_status(build_status)

    if failed_overall:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
