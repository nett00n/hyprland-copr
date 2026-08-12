#!/usr/bin/env python3
"""Stage 2: Download sources and build SRPMs (spectool + rpmbuild -bs).

Reads packages.yaml and build-report.db for spec stage results.
Skips packages where spec stage failed. Records SRPM paths in build-report.db.

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
import shutil
import sys
from pathlib import Path

from lib import build_db
from lib.config import setup_logging
from lib.paths import (
    ARCH,
    DISTRO,
    ROOT,
    SOURCES_DIR,
    get_package_log_dir,
    resolve_target,
)
from lib.reporting import event, status, verbose_proceed_check
from lib.source_lock import verify as verify_sources
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import apply_os_overrides, prepare_stage


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


def run_for_package(
    pkg: str,
    meta: dict,
    fedora_version: str,
    proceed: bool,
    target: str,
    run_id: int,
) -> bool:
    """Run SRPM build for a single package. Return True on success/skip, False on failure.

    Writes the srpm stage row for `pkg`.
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        event("srpm", target, pkg, "skip", reason=f"fedora:{fedora_version} skip")
        build_db.set_stage(
            pkg, "srpm", target, run_id, "skipped", reason="config: skip"
        )
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    has_devel = 1 if "devel" in meta else 0
    spec = ROOT / "packages" / pkg.lower() / f"{pkg.lower()}.spec"
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "10-srpm.log"
    log.unlink(missing_ok=True)

    # Skip if mock stage already succeeded AND SRPM file exists
    mock_entry = build_db.get_stage(pkg, "mock", target)
    prior_mock_state = mock_entry.get("state") if mock_entry else None
    srpm_entry = build_db.get_stage(pkg, "srpm", target)
    prior_srpm_path = srpm_entry.get("path") if srpm_entry else None
    srpm_exists = bool(prior_srpm_path) and Path(str(prior_srpm_path)).exists()
    if (
        proceed
        and verbose_proceed_check("mock", pkg, prior_mock_state, target)
        and srpm_exists
    ):
        status("srpm", pkg, "skip", target, "mock already succeeded")
        return True  # preserve existing srpm entry untouched

    # Skip if spec stage failed
    spec_entry = build_db.get_stage(pkg, "spec", target)
    spec_state = spec_entry.get("state", "") if spec_entry else ""
    if spec_state == "failed" or spec_entry is None:
        status("srpm", pkg, "skip", target, "spec failed")
        build_db.set_stage(
            pkg,
            "srpm",
            target,
            run_id,
            "skipped",
            version=ver,
            reason="spec failed",
            has_devel=has_devel,
        )
        return True

    ok, _, _ = run_cmd(["spectool", "-g", "-R", str(spec)], log)
    if not ok:
        status("srpm", pkg, "fail", target)
        build_db.set_stage(
            pkg,
            "srpm",
            target,
            run_id,
            "failed",
            version=ver,
            log=str(log.relative_to(ROOT)),
            has_devel=has_devel,
        )
        return False

    problems = verify_sources(pkg, meta, SOURCES_DIR)
    if problems:
        status("srpm", pkg, "fail", target, "source verify failed")
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as fh:
            fh.write("source verification failed:\n")
            for p in problems:
                fh.write(f"  {p}\n")
        build_db.set_stage(
            pkg,
            "srpm",
            target,
            run_id,
            "failed",
            version=ver,
            reason="source verify failed",
            log=str(log.relative_to(ROOT)),
            has_devel=has_devel,
        )
        return False

    copy_local_patches(pkg, meta)
    event("srpm", target, pkg, "run")
    ok, _, _ = run_cmd(["rpmbuild", "-bs", str(spec)], log)
    if not ok:
        status("srpm", pkg, "fail", target)
        build_db.set_stage(
            pkg,
            "srpm",
            target,
            run_id,
            "failed",
            version=ver,
            log=str(log.relative_to(ROOT)),
            has_devel=has_devel,
        )
        return False

    path = find_srpm(pkg)
    status("srpm", pkg, "ok", target)
    build_db.set_stage(
        pkg,
        "srpm",
        target,
        run_id,
        "success",
        version=ver,
        path=path,
        log=str(log.relative_to(ROOT)),
        has_devel=has_devel,
    )
    if path:
        # Absolute container path: /root/rpmbuild/SRPMS is a podman volume,
        # not under ROOT, so there's no repo-relative form to use.
        build_db.record_artifact(path, "rpmbuild-volume", "srpm", pkg, target, ver)
    return True


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

    packages = prepare_stage("srpm", target, proceed)

    failed = False
    for pkg, meta in packages.items():
        if not run_for_package(pkg, meta, fedora_version, proceed, target, run_id):
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
