#!/usr/bin/env python3
"""Stage 4: Submit SRPMs to Copr and record build IDs.

Reads packages.yaml and build-report.db for srpm stage results.
Skips packages where srpm stage failed or COPR_REPO is not set.
Records build IDs in build-report.db.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE              Build only this package (optional, comma-separated)
  FEDORA_VERSION       Fedora version to target (default: 43)
  MOCK_CHROOT          Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO            Copr repo slug, e.g. nett00n/hyprland (required)
  SKIP_PACKAGES        Skip these packages (optional, comma-separated)
  PROCEED_BUILD        Skip packages where copr stage already succeeded
  SYNCHRONOUS_COPR_BUILD  If 'true', wait for build completion (default: async with --nowait)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import sys
from typing import Any

from lib import build_db
from lib.config import setup_logging
from lib.copr import check_copr_credentials, parse_build_id, validate_copr_repo
from lib.paths import ARCH, DISTRO, ROOT, get_package_log_dir, resolve_target
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import apply_os_overrides, prepare_stage


def run_for_package(
    pkg: str,
    meta: dict,
    fedora_version: str,
    copr_repo: str,
    proceed: bool,
    target: str,
    run_id: int,
    synchronous: bool = False,
) -> bool:
    """Submit SRPM to Copr for a single package. Return True on success/skip, False on failure.

    Writes the copr stage row for `pkg`.

    If synchronous=False (default), uses --nowait flag for async submission.
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_db.set_stage(
            pkg, "copr", target, run_id, "skipped", reason="config: skip"
        )
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    has_devel = 1 if "devel" in meta else 0
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "30-copr.log"
    log.unlink(missing_ok=True)

    # Skip if copr stage already succeeded
    copr_entry = build_db.get_stage(pkg, "copr", target)
    prior_copr_state = copr_entry.get("state") if copr_entry else None
    if proceed and verbose_proceed_check("copr", pkg, prior_copr_state):
        status("copr", pkg, "skip", "already succeeded")
        return True

    srpm_entry = build_db.get_stage(pkg, "srpm", target)
    mock_entry = build_db.get_stage(pkg, "mock", target)
    srpm_state = srpm_entry.get("state", "") if srpm_entry else ""
    srpm_path = srpm_entry.get("path") if srpm_entry else None
    mock_state = mock_entry.get("state", "") if mock_entry else ""

    if (
        srpm_state in ("failed", "skipped")
        or not srpm_path
        or mock_state in ("failed", "skipped")
    ):
        blocker = (
            f"mock {mock_state}"
            if mock_state in ("failed", "skipped")
            else f"srpm {srpm_state}"
        )
        status("copr", pkg, "skip", blocker)
        build_db.set_stage(
            pkg,
            "copr",
            target,
            run_id,
            "skipped",
            version=ver,
            reason=blocker,
            has_devel=has_devel,
        )
        return True

    print(f"  [RUN]  copr: {pkg}", flush=True)
    cmd = ["copr-cli", "build"]
    if not synchronous:
        cmd.append("--nowait")
    cmd.extend([copr_repo, srpm_path])
    ok, stdout, _ = run_cmd(cmd, log)

    # In async mode: successful submission → "unknown" state (build is pending)
    # In sync mode: successful submission → "success", failed submission → "failed"
    if ok:
        state = "unknown" if not synchronous else "success"
    else:
        state = "failed"

    build_id = parse_build_id(stdout) if ok else None
    status("copr", pkg, "ok" if ok else "fail")

    extra: dict[str, Any] = {}
    if ok and synchronous:
        extra["completed_at"] = build_db.now_epoch()
    build_db.set_stage(
        pkg,
        "copr",
        target,
        run_id,
        state,
        version=ver,
        build_id=build_id,
        log=str(log.relative_to(ROOT)),
        has_devel=has_devel,
        **extra,
    )

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)
    copr_repo = os.environ.get("COPR_REPO", "")

    if not copr_repo:
        print(
            "error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)",
            file=sys.stderr,
        )
        sys.exit(2)
    if not validate_copr_repo(copr_repo):
        print(f"error: Invalid COPR_REPO format: {copr_repo}", file=sys.stderr)
        sys.exit(2)

    # Check credentials early
    if not check_copr_credentials():
        sys.exit(2)

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    synchronous = os.environ.get("SYNCHRONOUS_COPR_BUILD", "").lower() == "true"

    run_id = build_db.start_run(
        target,
        DISTRO,
        fedora_version,
        ARCH,
        copr_repo=copr_repo,
        package_filter=os.environ.get("PACKAGE", ""),
    )

    packages = prepare_stage("copr", target, proceed)

    failed = False
    print("\n=== copr ===")
    for pkg, meta in packages.items():
        if not run_for_package(
            pkg, meta, fedora_version, copr_repo, proceed, target, run_id, synchronous
        ):
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
