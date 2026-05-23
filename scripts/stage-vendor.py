#!/usr/bin/env python3
"""Stage 1b: Generate vendor tarballs.

Runs between stage-spec and stage-srpm. For each package that has
'golang' or 'cargo' in build_requires, generates a <name>-<version>-vendor.tar.gz
in ~/rpmbuild/SOURCES/ and embeds it into the subsequent SRPM so that
COPR cloud builds have all dependencies available offline.

Supports: Go (go mod vendor) and Rust (cargo vendor).

Skips packages where the spec stage failed.
Skips packages that don't require vendoring.
Skips packages whose vendor tarball already exists at the expected path.

Must be run with network access (before entering the mock chroot).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import sys

from lib.config import setup_logging
from lib.paths import ROOT, SOURCES_DIR, GITMODULES, get_package_log_dir
from lib.reporting import status
from lib.vendor import (
    VendorError,
    generate,
    is_go_package,
    is_rust_package,
    vendor_tarball_path,
)
from lib.version import nvr
from lib.gitmodules import parse_gitmodules
from lib.yaml_utils import (
    apply_os_overrides,
    init_stage,
    save_build_status,
)


def run_for_package(
    pkg: str,
    meta: dict,
    build_status: dict,
    fedora_version: str,
) -> bool:
    """Run vendoring for a single package. Return True on success/skip, False on failure.

    Updates build_status["stages"]["vendor"][pkg] in-place.
    Does not call save_build_status().
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_status["stages"]["vendor"][pkg] = {
            "state": "skipped",
            "version": None,
            "log": None,
            "force_run": False,
            "reason": "config: skip",
        }
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "05-vendor.log"
    log.unlink(missing_ok=True)

    # Skip if not a Go or Rust package
    if not (is_go_package(meta) or is_rust_package(meta)):
        build_status["stages"]["vendor"][pkg] = {
            "state": "skipped",
            "version": ver,
            "log": None,
            "force_run": False,
            "reason": "not-vendored",
        }
        return True

    # Skip if spec stage failed (read from build_status)
    spec_stage = build_status.get("stages", {}).get("spec", {})
    spec_state = spec_stage.get(pkg, {}).get("state", "")
    if spec_state == "failed" or (spec_stage and pkg not in spec_stage):
        status("vendor", pkg, "skip", "spec failed")
        build_status["stages"]["vendor"][pkg] = {
            "state": "skipped",
            "version": ver,
            "log": None,
            "force_run": False,
            "reason": "spec failed",
        }
        return True

    version = str(meta["version"])
    tarball = vendor_tarball_path(pkg, version, SOURCES_DIR)

    # For Rust packages, also check if the source tarball exists
    is_rust = is_rust_package(meta)
    source_tarball = None
    if is_rust:
        source_tarball = SOURCES_DIR / f"{pkg}-{version}.tar.gz"
        tarballs_exist = tarball.exists() and source_tarball.exists()
    else:
        tarballs_exist = tarball.exists()

    if tarballs_exist:
        status("vendor", pkg, "ok")
        build_status["stages"]["vendor"][pkg] = {
            "state": "success",
            "version": ver,
            "path": str(tarball),
            "log": None,
            "force_run": False,
        }
        return True

    try:
        print(f"  [RUN]  vendor: {pkg}", flush=True)
        pkg_url = meta.get("url", "").rstrip("/")
        submodule_path = None
        submodules = parse_gitmodules(ROOT / GITMODULES)
        if submodules:
            for mod in submodules:
                mod_url = mod.get("url", "").rstrip("/")
                if pkg_url.removesuffix(".git") == mod_url.removesuffix(".git"):
                    submodule_path = ROOT / mod.get("path", "")
                    break
        generate(pkg, meta, tarball, log_path=log, submodule_path=submodule_path)
        status("vendor", pkg, "ok")
        build_status["stages"]["vendor"][pkg] = {
            "state": "success",
            "version": ver,
            "path": str(tarball),
            "log": str(log.relative_to(ROOT)),
            "force_run": False,
        }
        return True
    except VendorError as exc:
        status("vendor", pkg, "fail")
        with open(log, "a") as fh:
            fh.write(f"error: {exc}\n")
        build_status["stages"]["vendor"][pkg] = {
            "state": "failed",
            "version": ver,
            "path": None,
            "log": str(log.relative_to(ROOT)),
            "force_run": False,
        }
        return False


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")

    packages, build_status = init_stage("vendor")
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    failed = False
    print("\n=== vendor ===")
    for pkg, meta in packages.items():
        if not run_for_package(pkg, meta, build_status, fedora_version):
            failed = True

    save_build_status(build_status)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
