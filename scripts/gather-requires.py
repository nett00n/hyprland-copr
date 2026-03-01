#!/usr/bin/env python3
"""Suggest requires: entries for packages.yaml from built RPMs.

Queries SONAME dependencies from each RPM, resolves them to package names
via rpm --whatprovides, and prints a YAML-ready requires: list.

Base system packages (glibc, libgcc, libstdc++, libm) are excluded — RPM
handles those automatically via auto-dependency generation.

Usage:
    python3 scripts/gather-requires.py PACKAGE.rpm [PACKAGE2.rpm ...]
"""

import re
import subprocess
import sys
from pathlib import Path

# Bare SONAME entry: libfoo.so.N()(64bit)
_BARE_SONAME = re.compile(r"^(lib\S+\.so\.\d+)\(\)\(64bit\)$")

# Base system packages to exclude — auto-deps handle these
SKIP_PACKAGES = frozenset(
    {
        "glibc",
        "libgcc",
        "libstdc++",
        "libm",
        "basesystem",
    }
)


def rpm(*args: str) -> list[str]:
    result = subprocess.run(
        ["rpm", *args],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def bare_sonames(rpm_path: str) -> list[str]:
    """Return unique bare SONAME entries from an RPM's Requires."""
    seen: set[str] = set()
    out: list[str] = []
    for line in rpm("-qp", "--requires", rpm_path):
        line = line.strip()
        if _BARE_SONAME.match(line) and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def whatprovides(soname: str) -> str | None:
    """Resolve a SONAME to its base package name, or None if not found."""
    lines = rpm("-q", "--whatprovides", "--queryformat", "%{NAME}\\n", soname)
    names = [ln.strip() for ln in lines if ln.strip() and "not owned" not in ln]
    if not names:
        return None
    # Prefer shortest name (base package over -libs/-debuginfo variants)
    return sorted(names, key=len)[0]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: gather-requires.py PACKAGE.rpm [PACKAGE2.rpm ...]")

    for rpm_path in sys.argv[1:]:
        print(f"# {Path(rpm_path).name}")
        sonames = bare_sonames(rpm_path)

        pkg_names: set[str] = set()
        unresolved: list[str] = []

        for soname in sonames:
            pkg = whatprovides(soname)
            if pkg is None:
                unresolved.append(soname)
            elif pkg not in SKIP_PACKAGES:
                pkg_names.add(pkg)

        if pkg_names:
            print("requires:")
            for name in sorted(pkg_names):
                print(f"  - {name}")

        if unresolved:
            print("# unresolved (not in local rpmdb):")
            for s in sorted(unresolved):
                print(f"#   - {s}")

        print()


if __name__ == "__main__":
    main()
