#!/usr/bin/env python3
"""Stage 0: Validate packages.yaml entries.

Checks required fields, deprecated sections, file placement, build_system
validity, and .gitmodules conventions.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Validate only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
"""

import logging
import os
import sys

from lib.config import setup_logging
from lib.paths import ROOT
from lib.reporting import status
from lib.validation import (
    validate_gitmodules,
    validate_group_membership,
    validate_no_duplicate_urls,
    validate_package,
)
from lib.yaml_utils import (
    apply_os_overrides,
    init_stage,
    save_build_status,
)


def run_for_package(
    pkg: str,
    meta: dict,
    all_packages: dict,
    build_status: dict,
    fedora_version: str,
) -> bool:
    """Validate a single package. Return True if OK or skipped, False if failed.

    Updates build_status["stages"]["validate"][pkg] in-place.
    Does not call save_build_status().
    """
    resolved = apply_os_overrides(meta, fedora_version)
    if resolved.get("_skip"):
        status("validate", pkg, "skip")
        build_status["stages"]["validate"][pkg] = {
            "state": "skipped",
            "force_run": False,
            "reason": "config: skip",
        }
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

    build_status["stages"]["validate"][pkg] = {
        "state": state,
        "errors": len(errors),
        "warnings": len(warnings),
        "force_run": False,
    }
    return state == "success"


def run_global_checks(all_packages: dict, build_status: dict) -> bool:
    """Run global validation checks (group membership and .gitmodules).

    Updates build_status["stages"]["validate"] in-place.
    Returns True if all checks pass, False if any failed.
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

    all_packages, packages, build_status = init_stage("validate", include_all=True)

    print("\n=== validate ===")

    for pkg, meta in packages.items():
        run_for_package(pkg, meta, all_packages, build_status, fedora_version)

    global_ok = run_global_checks(all_packages, build_status)
    save_build_status(build_status)

    if not global_ok:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
