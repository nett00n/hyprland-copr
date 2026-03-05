#!/usr/bin/env python3
"""Stage 1b: Generate Go vendor tarballs.

Runs between stage-spec and stage-srpm. For each package that has
'golang' in build_requires, generates a <name>-<version>-vendor.tar.gz
in ~/rpmbuild/SOURCES/ and embeds it into the subsequent SRPM so that
COPR cloud builds have all dependencies available offline.

Skips packages where the spec stage failed.
Skips packages that are not Go (no 'golang' in build_requires).
Skips packages whose vendor tarball already exists at the expected path.

Must be run with network access (before entering the mock chroot).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
"""

import os
import sys
from pathlib import Path

from lib.paths import LOG_DIR, ROOT
from lib.reporting import status
from lib.vendor import VendorError, generate, is_go_package, vendor_tarball_path
from lib.version import nvr
from lib.yaml_utils import get_packages, load_build_status, save_build_status

SOURCES_DIR = Path.home() / "rpmbuild" / "SOURCES"


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    package_filter = os.environ.get("PACKAGE", "")

    all_packages = get_packages()
    if package_filter:
        names = [n.strip() for n in package_filter.split(",") if n.strip()]
        unknown = [n for n in names if n not in all_packages]
        if unknown:
            sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
        packages = {n: all_packages[n] for n in names}
    else:
        packages = all_packages

    LOG_DIR.mkdir(exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    build_status = load_build_status()
    spec_stage = build_status.get("stages", {}).get("spec", {})
    build_status.setdefault("stages", {})["vendor"] = {}

    failed = False
    print("\n=== vendor ===")
    for pkg, meta in packages.items():
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        log = LOG_DIR / f"{pkg}-05-vendor.log"
        log.unlink(missing_ok=True)

        # Skip if not a Go package
        if not is_go_package(meta):
            build_status["stages"]["vendor"][pkg] = {"state": "skipped", "version": ver, "log": None}
            continue

        # Skip if spec stage failed
        spec_state = spec_stage.get(pkg, {}).get("state", "")
        if spec_state == "failed" or (spec_stage and pkg not in spec_stage):
            status("vendor", pkg, "skip")
            build_status["stages"]["vendor"][pkg] = {"state": "skipped", "version": ver, "log": None}
            continue

        version = str(meta["version"])
        tarball = vendor_tarball_path(pkg, version, SOURCES_DIR)

        if tarball.exists():
            status("vendor", pkg, "ok")
            build_status["stages"]["vendor"][pkg] = {
                "state": "success",
                "version": ver,
                "path": str(tarball),
                "log": None,
            }
            continue

        try:
            generate(pkg, meta, tarball, log_path=log)
            status("vendor", pkg, "ok")
            build_status["stages"]["vendor"][pkg] = {
                "state": "success",
                "version": ver,
                "path": str(tarball),
                "log": str(log.relative_to(ROOT)),
            }
        except VendorError as exc:
            failed = True
            status("vendor", pkg, "fail")
            with open(log, "a") as fh:
                fh.write(f"error: {exc}\n")
            build_status["stages"]["vendor"][pkg] = {
                "state": "failed",
                "version": ver,
                "path": None,
                "log": str(log.relative_to(ROOT)),
            }

    save_build_status(build_status)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
