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
Otherwise, checks the content-addressed vendor store (lib/vendor_store.py,
.cache/vendor/) before running `cargo vendor`/`go mod vendor` -- a hit there
is copied into place instead of rebuilt, since that store is shared across
every FEDORA_VERSION target.

Must be run with network access (before entering the mock chroot).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import shutil
import sys

from lib import build_db, vendor_store
from lib.config import setup_logging
from lib.paths import ARCH, DISTRO, ROOT, SOURCES_DIR, resolve_target
from lib.reporting import event, status
from lib.vendor import (
    VendorError,
    generate,
    is_go_package,
    is_rust_package,
    vendor_tarball_path,
)
from lib.version import nvr
from lib.yaml_utils import apply_os_overrides, prepare_stage

# Sentinel target/realm for the content-addressed vendor store (lib/vendor_store.py):
# one entry serves every real target, so it's recorded outside the per-target
# rpmbuild-volume namespace those rows otherwise live in.
_VENDOR_STORE_REALM = "vendor-store"


def run_for_package(
    pkg: str,
    meta: dict,
    fedora_version: str,
    target: str,
    run_id: int,
    all_packages: dict | None = None,
) -> bool:
    """Run vendoring for a single package. Return True on success/skip, False on failure.

    Writes the vendor stage row for `pkg`. `all_packages` feeds the vendor
    store's input hash (lib.cache.compute_input_hashes) the same package
    universe every other stage's cache uses; defaults to just `{pkg: meta}`
    for standalone callers/tests that don't have it handy.
    """
    all_packages = all_packages if all_packages is not None else {pkg: meta}
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        event("vendor", target, pkg, "skip", reason=f"fedora:{fedora_version} skip")
        build_db.set_stage(
            pkg, "vendor", target, run_id, "skipped", reason="config: skip"
        )
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    pkg_log_dir = ROOT / "logs" / "build" / pkg
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "05-vendor.log"
    log.unlink(missing_ok=True)

    # Callers that invoke run_for_package() directly (full-cycle.py's
    # per-package pipeline) never go through main(), which is the only place
    # this used to be created -- a fresh rpmbuild volume with no prior
    # `make stage-vendor` run then hits generate()'s tarfile.open() with a
    # missing parent dir (FileNotFoundError).
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # Skip if not a Go or Rust package
    if not (is_go_package(meta) or is_rust_package(meta)):
        build_db.set_stage(
            pkg, "vendor", target, run_id, "skipped", version=ver, reason="not-vendored"
        )
        return True

    # Skip if spec stage failed
    spec_entry = build_db.get_stage(pkg, "spec", target)
    spec_state = spec_entry.get("state", "") if spec_entry else ""
    if spec_state == "failed" or spec_entry is None:
        status("vendor", pkg, "skip", target, "spec failed")
        build_db.set_stage(
            pkg, "vendor", target, run_id, "skipped", version=ver, reason="spec failed"
        )
        return True

    version = str(meta["version"])
    tarball = vendor_tarball_path(pkg, version, SOURCES_DIR)
    tarballs_exist = tarball.exists()

    def _record_tarballs() -> None:
        # Absolute container paths: SOURCES_DIR is /root/rpmbuild/SOURCES, a
        # podman volume, not under ROOT.
        build_db.record_artifact(
            str(tarball), "rpmbuild-volume", "vendor", pkg, target, ver
        )

    def _record_store(store_path) -> None:
        # One row per (pkg, input-hash), shared across every target -- see
        # lib/vendor_store.py.
        build_db.record_artifact(
            str(store_path),
            _VENDOR_STORE_REALM,
            "vendor",
            pkg,
            _VENDOR_STORE_REALM,
            version,
        )

    if tarballs_exist:
        status("vendor", pkg, "ok", target)
        build_db.set_stage(
            pkg, "vendor", target, run_id, "success", version=ver, path=str(tarball)
        )
        _record_tarballs()
        return True

    store_hit = vendor_store.find(pkg, meta, all_packages)
    if store_hit is not None:
        event("vendor", target, pkg, "ok", reason="vendor-store hit")
        tarball.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(store_hit, tarball)
        status("vendor", pkg, "ok", target)
        build_db.set_stage(
            pkg,
            "vendor",
            target,
            run_id,
            "success",
            version=ver,
            path=str(tarball),
            reason="vendor-store hit",
        )
        _record_tarballs()
        _record_store(store_hit)
        return True

    try:
        event("vendor", target, pkg, "run")
        generate(pkg, meta, tarball, log_path=log, fedora_version=fedora_version)
        store_path = vendor_store.store(pkg, meta, all_packages, tarball)
        status("vendor", pkg, "ok", target)
        build_db.set_stage(
            pkg,
            "vendor",
            target,
            run_id,
            "success",
            version=ver,
            path=str(tarball),
            log=str(log.relative_to(ROOT)),
        )
        _record_tarballs()
        _record_store(store_path)
        return True
    except VendorError as exc:
        status("vendor", pkg, "fail", target)
        with open(log, "a") as fh:
            fh.write(f"error: {exc}\n")
        build_db.set_stage(
            pkg,
            "vendor",
            target,
            run_id,
            "failed",
            version=ver,
            log=str(log.relative_to(ROOT)),
        )
        return False


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    run_id = build_db.start_run(
        target,
        DISTRO,
        fedora_version,
        ARCH,
        package_filter=os.environ.get("PACKAGE", ""),
    )

    packages = prepare_stage("vendor", target, proceed)

    failed = False
    for pkg, meta in packages.items():
        if not run_for_package(pkg, meta, fedora_version, target, run_id, packages):
            failed = True

    build_db.finish_run(run_id, "failed" if failed else "ok")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
