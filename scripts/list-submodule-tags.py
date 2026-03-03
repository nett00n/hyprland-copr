#!/usr/bin/env python3
"""Backwards-compatible dispatcher for submodule tag management.

Delegates to the appropriate focused script based on subcommand:
  list-tags  -> scripts/list-tags.py
  update     -> scripts/update-versions.py
  add        -> scripts/scaffold-package.py

Usage (unchanged from previous version):
    python3 scripts/list-submodule-tags.py list-tags [PACKAGE]
    python3 scripts/list-submodule-tags.py update
    python3 scripts/list-submodule-tags.py add PACKAGE
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

SUBCOMMAND_MAP = {
    "list-tags": SCRIPTS / "list-tags.py",
    "update": SCRIPTS / "update-versions.py",
    "add": SCRIPTS / "scaffold-package.py",
}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in SUBCOMMAND_MAP:
        print(
            "usage: list-submodule-tags.py {list-tags|update|add} [PACKAGE]",
            file=sys.stderr,
        )
        print(
            "       (delegates to list-tags.py, update-versions.py, scaffold-package.py)",
            file=sys.stderr,
        )
        sys.exit(1 if args else 0)

    script = SUBCOMMAND_MAP[args[0]]
    result = subprocess.run([sys.executable, str(script)] + args[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
