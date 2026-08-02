#!/usr/bin/env python3
"""Stage 0: Validate packages.yaml entries.

Checks required fields, deprecated sections, file placement, build_system
validity, and .gitmodules conventions.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Validate only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
"""

import logging
import os
import sys

from lib import build_db
from lib.config import setup_logging
from lib.gitmodules import parse_gitmodules
from lib.paths import ARCH, DISTRO, GITMODULES, ROOT, resolve_target
from lib.reporting import status
from lib.validation import (
    validate_gitmodules,
    validate_group_membership,
    validate_no_duplicate_urls,
    validate_package,
    validate_submodule_url_resolution,
)
from lib.yaml_utils import apply_os_overrides, prepare_stage


def run_for_package(
    pkg: str,
    meta: dict,
    all_packages: dict,
    fedora_version: str,
    target: str,
    run_id: int,
) -> bool:
    """Validate a single package. Return True if OK or skipped, False if failed.

    Writes the validate stage row for `pkg`.
    """
    resolved = apply_os_overrides(meta, fedora_version)
    if resolved.get("_skip"):
        status("validate", pkg, "skip")
        build_db.set_stage(
            pkg, "validate", target, run_id, "skipped", reason="config: skip"
        )
        return True

    print(f"  [RUN]  validate: {pkg}", flush=True)
    errors, warnings = validate_package(pkg, resolved, all_packages)

    state = "failed" if errors else "success"
    if errors:
        status("validate", pkg, "fail")
        for e in errors:
            print(f"    error: {e}")
    else:
        status("validate", pkg, "ok")

    for w in warnings:
        print(f"    warn: {w}")

    build_db.set_stage(
        pkg,
        "validate",
        target,
        run_id,
        state,
        errors=len(errors),
        warnings=len(warnings),
    )
    return state == "success"


def run_global_checks(all_packages: dict) -> bool:
    """Run global validation checks (group membership and .gitmodules).

    Returns True if all checks pass, False if any failed. Prints results;
    does not write any stage row (these checks aren't per-package).
    """
    failed = False
    total_errors = 0
    total_warnings = 0

    # Validate group membership
    grp_errors, grp_warnings = validate_group_membership(all_packages)
    if grp_errors:
        failed = True
        status("validate", "groups", "fail")
        for e in grp_errors:
            print(f"    error: {e}")
    else:
        status("validate", "groups", "ok")
    total_errors += len(grp_errors)
    total_warnings += len(grp_warnings)

    # Warn on packages sharing a url (see validate_no_duplicate_urls docstring)
    dup_errors, dup_warnings = validate_no_duplicate_urls(all_packages)
    for w in dup_warnings:
        print(f"    warn: {w}")
    total_errors += len(dup_errors)
    total_warnings += len(dup_warnings)

    # Warn when a package's url doesn't resolve to any .gitmodules submodule
    # (see validate_submodule_url_resolution docstring, docs/bugs.md BUG-0013)
    modules = parse_gitmodules(GITMODULES) if GITMODULES.exists() else []
    url_errors, url_warnings = validate_submodule_url_resolution(
        all_packages, modules
    )
    for w in url_warnings:
        print(f"    warn: {w}")
    total_errors += len(url_errors)
    total_warnings += len(url_warnings)

    # Validate .gitmodules
    gm_errors, gm_warnings = validate_gitmodules(ROOT)
    if gm_errors:
        failed = True
        status("validate", ".gitmodules", "fail")
        for e in gm_errors:
            print(f"    error: {e}")
    else:
        status("validate", ".gitmodules", "ok")
    for w in gm_warnings:
        print(f"    warn: {w}")
    total_errors += len(gm_errors)
    total_warnings += len(gm_warnings)

    if total_warnings:
        print(f"\n  {total_warnings} warning(s) total")
    if failed:
        print(f"\n  {total_errors} error(s) found — validation failed", file=sys.stderr)

    return not failed


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

    all_packages, packages = prepare_stage(
        "validate", target, proceed, include_all=True
    )

    print("\n=== validate ===")

    for pkg, meta in packages.items():
        run_for_package(pkg, meta, all_packages, fedora_version, target, run_id)

    global_ok = run_global_checks(all_packages)
    build_db.finish_run(run_id, "ok" if global_ok else "failed")

    if not global_ok:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
