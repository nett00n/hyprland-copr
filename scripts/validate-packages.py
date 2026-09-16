#!/usr/bin/env python3
"""Validate packages.yaml and .gitmodules for configuration issues.

Thin front-end over lib.validation -- the same validator scripts/stage-validate.py
runs as the real build's stage 0. The two used to be independently-diverged
validators (docs/BUGS.md, formerly BUG-0012): a package could pass this fast,
no-container pre-commit gate and still fail build validation, or vice versa. Now
a passing `make validate-packages` implies `make stage-validate` will pass too.

Checks (see lib.validation for the authoritative list):
- Required fields, source.archives, build system, devel-file placement
- packages.yaml scalar types match FIELD_TYPES (#BUG-0097)
- Vendoring trigger cross-checked against declared source/prep (#BUG-0089)
- Self-dependencies and invalid depends_on references (case-insensitive)
- Unknown auto_update.release_type values
- fedora: override blocks only using the supported `skip` key
- Group membership
- .gitmodules conventions: submodules/ path prefix, https:// urls,
  ignore = dirty
- A package's url not matching any .gitmodules submodule url (warning only)
- .env assigning the same key more than once (warning only; #BUG-0052)
- No duplicate/misfiled #BUG-/#TODO- tracker IDs in docs/BUGS.md, docs/TODO.md
  (#BUG-0073)
- A commit-tracked package outrunning a tag-pinned depends_on (warning only,
  offline; #BUG-0056)
"""

import sys

from lib.gitmodules import parse_gitmodules
from lib.paths import GITMODULES
from lib.validation import (
    validate_dependency_drift,
    validate_env_file,
    validate_gitmodules,
    validate_group_membership,
    validate_no_duplicate_urls,
    validate_package,
    validate_submodule_url_resolution,
    validate_tracker_ids,
)
from lib.yaml_utils import get_packages


def main() -> None:
    """Validate packages.yaml and .gitmodules. #COPR-0010"""
    packages = get_packages()

    errors: list[str] = []
    warnings: list[str] = []

    for pkg, meta in packages.items():
        pkg_errors, pkg_warnings = validate_package(pkg, meta, packages)
        errors.extend(f"  {pkg}: {e}" for e in pkg_errors)
        warnings.extend(f"  {pkg}: {w}" for w in pkg_warnings)

    grp_errors, grp_warnings = validate_group_membership(packages)
    errors.extend(f"  {e}" for e in grp_errors)
    warnings.extend(f"  {w}" for w in grp_warnings)

    dup_errors, dup_warnings = validate_no_duplicate_urls(packages)
    errors.extend(f"  {e}" for e in dup_errors)
    warnings.extend(f"  {w}" for w in dup_warnings)

    modules = parse_gitmodules(GITMODULES) if GITMODULES.exists() else []
    url_errors, url_warnings = validate_submodule_url_resolution(packages, modules)
    errors.extend(f"  {e}" for e in url_errors)
    warnings.extend(f"  {w}" for w in url_warnings)

    gitmodules_errors, gitmodules_warnings = validate_gitmodules()
    warnings.extend(f"  {w}" for w in gitmodules_warnings)

    warnings.extend(f"  {w}" for w in validate_env_file())

    errors.extend(f"  {e}" for e in validate_tracker_ids())

    _, drift_warnings = validate_dependency_drift(packages)
    warnings.extend(f"  {w}" for w in drift_warnings)

    if errors:
        print("error: packages.yaml validation failed:", file=sys.stderr)
        for err in errors:
            print(err, file=sys.stderr)
        sys.exit(1)

    if gitmodules_errors:
        print("error: .gitmodules validation failed:", file=sys.stderr)
        for err in gitmodules_errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)

    if warnings:
        print(
            "warning: packages.yaml/.gitmodules validation warning(s):", file=sys.stderr
        )
        for warn in warnings:
            print(warn, file=sys.stderr)

    print("✓ packages.yaml validation passed")
    print("✓ .gitmodules validation passed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
