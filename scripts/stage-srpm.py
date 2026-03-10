#!/usr/bin/env python3
"""Stage 2: Download sources and build SRPMs (spectool + rpmbuild -bs).

Reads packages.yaml and logs/build-status.yaml for spec stage results.
Skips packages where spec stage failed. Records SRPM paths in build-status.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  PROCEED_BUILD   Skip packages where mock stage already succeeded
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from lib.paths import LOG_DIR, ROOT
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    filter_packages,
    get_packages,
    load_build_status,
    save_build_status,
)


SOURCES_DIR = Path.home() / "rpmbuild" / "SOURCES"


def copy_local_patches(pkg: str, meta: dict) -> None:
    patches = meta.get("source", {}).get("patches", [])
    if not patches:
        return
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    pkg_dir = ROOT / "packages" / pkg.lower()
    for patch in patches:
        src = pkg_dir / patch
        if src.exists():
            shutil.copy2(src, SOURCES_DIR / patch)


def find_srpm(pkg: str) -> str | None:
    srpm_dir = Path.home() / "rpmbuild" / "SRPMS"
    matches = sorted(
        srpm_dir.glob(f"{pkg.lower()}-*.src.rpm"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(matches[0]) if matches else None


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    package_filter = os.environ.get("PACKAGE", "")

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)

    LOG_DIR.mkdir(exist_ok=True)
    build_status = load_build_status()
    spec_stage = build_status.get("stages", {}).get("spec", {})

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    stages = build_status.setdefault("stages", {})
    if not proceed:
        stages["srpm"] = {}
    stages.setdefault("srpm", {})

    failed = False
    print("\n=== srpm ===")
    for pkg, meta in packages.items():
        meta = apply_os_overrides(meta, fedora_version)
        if meta.get("_skip"):
            print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
            build_status["stages"]["srpm"][pkg] = {
                "state": "skipped",
                "version": None,
                "path": None,
                "log": None,
            }
            continue
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        has_devel = "devel" in meta
        spec = ROOT / "packages" / pkg.lower() / f"{pkg.lower()}.spec"
        log = LOG_DIR / f"{pkg}-10-srpm.log"
        log.unlink(missing_ok=True)

        # Skip if mock stage already succeeded
        prior_mock_state = (
            build_status.get("stages", {}).get("mock", {}).get(pkg, {}).get("state")
        )
        if proceed and verbose_proceed_check("mock", pkg, prior_mock_state):
            status("srpm", pkg, "skip", "mock already succeeded")
            continue  # preserve existing srpm entry untouched

        # Skip if spec stage failed
        spec_state = spec_stage.get(pkg, {}).get("state", "")
        if spec_state == "failed" or (spec_stage and pkg not in spec_stage):
            status("srpm", pkg, "skip", "spec failed")
            entry: dict[str, Any] = {
                "state": "skipped",
                "version": ver,
                "path": None,
                "log": None,
            }
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "skipped", "version": ver}}
            build_status["stages"]["srpm"][pkg] = entry
            continue

        ok, _, _ = run_cmd(["spectool", "-g", "-R", str(spec)], log)
        if not ok:
            failed = True
            status("srpm", pkg, "fail")
            entry = {
                "state": "failed",
                "version": ver,
                "path": None,
                "log": str(log.relative_to(ROOT)),
            }
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "failed", "version": ver}}
            build_status["stages"]["srpm"][pkg] = entry
            continue

        copy_local_patches(pkg, meta)
        ok, _, _ = run_cmd(["rpmbuild", "-bs", str(spec)], log)
        if not ok:
            failed = True
            status("srpm", pkg, "fail")
            entry = {
                "state": "failed",
                "version": ver,
                "path": None,
                "log": str(log.relative_to(ROOT)),
            }
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "failed", "version": ver}}
            build_status["stages"]["srpm"][pkg] = entry
            continue

        path = find_srpm(pkg)
        status("srpm", pkg, "ok")
        entry = {
            "state": "success",
            "version": ver,
            "path": path,
            "log": str(log.relative_to(ROOT)),
        }
        if has_devel:
            entry["subpackages"] = {"devel": {"state": "success", "version": ver}}
        build_status["stages"]["srpm"][pkg] = entry
        save_build_status(build_status)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
