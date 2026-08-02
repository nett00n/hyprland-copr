#!/usr/bin/env python3
"""Validate packages.yaml and .gitmodules for configuration issues.

Checks for:
- Self-dependencies (package depends on itself)
- Invalid dependency references (depends_on references non-existent packages)
- Unknown auto_update.release_type values
- Missing ignore=dirty in .gitmodules (all submodules must have it)
- A package's url not matching any .gitmodules submodule url (warning only)
"""

import sys
from configparser import ConfigParser

import yaml

from lib.version import RELEASE_TYPES


def validate_gitmodules() -> list[str]:
    """Validate .gitmodules for missing ignore=dirty settings.

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    try:
        config = ConfigParser()
        config.read(".gitmodules")
    except Exception as e:
        errors.append(f"  Failed to parse .gitmodules: {e}")
        return errors

    for section in config.sections():
        if not section.startswith("submodule "):
            continue

        # Check if ignore = dirty is set
        if not config.has_option(section, "ignore"):
            submodule_name = section.replace('submodule "', "").replace('"', "")
            errors.append(
                f"  {submodule_name}: missing 'ignore = dirty' in .gitmodules"
            )
        elif config.get(section, "ignore") != "dirty":
            submodule_name = section.replace('submodule "', "").replace('"', "")
            current = config.get(section, "ignore")
            errors.append(
                f"  {submodule_name}: ignore={current}, should be 'ignore = dirty'"
            )

    return errors


def collect_gitmodules_urls() -> set[str]:
    """Return the set of submodule urls declared in .gitmodules."""
    config = ConfigParser()
    config.read(".gitmodules")
    return {
        config.get(section, "url")
        for section in config.sections()
        if config.has_option(section, "url")
    }


def validate_submodule_urls(packages: dict, gitmodules_urls: set[str]) -> list[str]:
    """Warn when a package's url won't resolve to any .gitmodules submodule.

    update-versions.py resolves each package's submodule via an EXACT string
    match against .gitmodules urls -- a stray or missing trailing `.git`
    means the package's auto_update silently never fires, with no error or
    warning at update time (see docs/bugs.md BUG-0013: two packages went
    weeks with no update before this was noticed by hand). Warning only,
    since not every packages.yaml entry necessarily tracks a live submodule.

    Returns:
        List of warning messages (empty if all urls resolve)
    """
    warnings = []
    for pkg, meta in packages.items():
        url = (meta or {}).get("url", "")
        if url and url not in gitmodules_urls:
            warnings.append(
                f"  {pkg}: url '{url}' does not match any .gitmodules submodule url"
            )
    return warnings


def main() -> None:
    """Validate packages.yaml and .gitmodules."""
    with open("packages.yaml") as f:
        packages = yaml.safe_load(f)

    if not packages:
        print("error: packages.yaml is empty or invalid")
        sys.exit(1)

    errors = []

    for pkg, config in packages.items():
        deps = config.get("depends_on", [])

        # Check for self-dependency
        if pkg in deps:
            errors.append(
                f"  {pkg}: self-dependency detected (remove '{pkg}' from depends_on)"
            )

        # Check for invalid dependencies
        for dep in deps:
            if dep not in packages:
                errors.append(
                    f"  {pkg}: invalid dependency '{dep}' (not found in packages.yaml)"
                )

        # Check auto_update.release_type -- an unrecognized type used to match
        # no dispatch branch in update-versions.py and silently fall through
        # to the default (semver-or-commit) path instead of erroring here
        # (see docs/bugs.md BUG-0014, e.g. mpvpaper's `latest-tag`).
        release_type = ((config or {}).get("auto_update") or {}).get("release_type")
        if release_type and release_type not in RELEASE_TYPES:
            errors.append(
                f"  {pkg}: unknown auto_update.release_type '{release_type}' "
                f"(valid: {', '.join(sorted(RELEASE_TYPES))})"
            )

    # Validate .gitmodules
    gitmodules_errors = validate_gitmodules()
    gitmodules_urls = collect_gitmodules_urls()
    url_warnings = validate_submodule_urls(packages, gitmodules_urls)

    if errors:
        print("error: packages.yaml validation failed:", file=sys.stderr)
        for err in errors:
            print(err, file=sys.stderr)
        sys.exit(1)

    if gitmodules_errors:
        print("error: .gitmodules validation failed:", file=sys.stderr)
        for err in gitmodules_errors:
            print(err, file=sys.stderr)
        sys.exit(1)

    if url_warnings:
        print("warning: package url(s) don't match .gitmodules:", file=sys.stderr)
        for warn in url_warnings:
            print(warn, file=sys.stderr)

    print("✓ packages.yaml validation passed")
    print("✓ .gitmodules validation passed")


if __name__ == "__main__":
    main()
