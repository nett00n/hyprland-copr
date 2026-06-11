#!/usr/bin/env python3
"""Validate packages.yaml and .gitmodules for configuration issues.

Checks for:
- Self-dependencies (package depends on itself)
- Invalid dependency references (depends_on references non-existent packages)
- Missing ignore=dirty in .gitmodules (all submodules must have it)
"""

import sys
from configparser import ConfigParser

import yaml


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

    # Validate .gitmodules
    gitmodules_errors = validate_gitmodules()

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

    print("✓ packages.yaml validation passed")
    print("✓ .gitmodules validation passed")


if __name__ == "__main__":
    main()
