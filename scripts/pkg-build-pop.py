#!/usr/bin/env python3
"""Remove mock and copr build status entries for packages.

Environment variables:
  PACKAGE         Comma-separated list of packages (optional; all packages if empty)
  FEDORA_VERSION  Fedora version to target (default: 44)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)

Exit/output semantics:
  - An unknown name in PACKAGE exits non-zero, naming every unresolved query.
  - An empty package selection (PACKAGE unset and no packages defined) prints
    "nothing to do" on stderr and exits 0.
  - Otherwise prints which packages actually had mock/copr rows cleared, or
    "nothing to clear" if none of the resolved packages had any.
"""

import os
import sys

from lib import build_db
from lib.paths import resolve_target
from lib.yaml_utils import find_package_name, get_packages


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "44")
    target = resolve_target(fedora_version, os.environ.get("MOCK_CHROOT", ""))

    package_env = os.environ.get("PACKAGE", "")
    if package_env:
        all_packages = get_packages()
        pkgs = []
        unknown = []
        for name in [n.strip() for n in package_env.split(",") if n.strip()]:
            key = find_package_name(all_packages, name)
            if key is None:
                unknown.append(name)
            else:
                pkgs.append(key)
        if unknown:
            sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
    else:
        pkgs = list(get_packages())

    if not pkgs:
        print("nothing to do", file=sys.stderr)
        sys.exit(0)

    affected = build_db.set_force_run(pkgs, ("mock", "copr"), target)
    if affected:
        print(f"cleared mock/copr for: {', '.join(affected)}")
    else:
        print(
            f"nothing to clear (mock/copr already empty for: {', '.join(sorted(pkgs))})"
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
