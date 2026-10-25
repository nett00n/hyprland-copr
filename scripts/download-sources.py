#!/usr/bin/env python3
"""Download each package's Source files into ~/rpmbuild/SOURCES with spectool.

Backs `make sources`, which verifies the result against sources.lock.yaml
afterwards (`make check-checksums`). Needs network access.

Environment variables:
  PACKAGE         Download only this package (optional, comma-separated)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  CMD_TIMEOUT     Per-package spectool timeout in seconds (default: 3600)
"""

import os
import sys

from lib.paths import ROOT
from lib.subprocess_utils import run_cmd
from lib.yaml_utils import filter_packages, get_packages, skip_packages

HIGHLIGHT_PREFIX = "█▓▒░"


def main() -> int:
    """#COPR-0002: run `spectool -g -R` for every selected package.

    Every spec is checked for existence first, so a missing one aborts the run
    before anything is downloaded. Returns 1 on a missing spec or a failed download.
    """
    selected = filter_packages(get_packages(), os.environ.get("PACKAGE", ""))
    names = list(skip_packages(selected, os.environ.get("SKIP_PACKAGES", "")))

    specs = {name: ROOT / "packages" / name / f"{name}.spec" for name in names}
    for name, spec in specs.items():
        if not spec.is_file():
            print(
                f"{HIGHLIGHT_PREFIX} ✗ sources: {name} - spec file not found: "
                f"{spec.relative_to(ROOT)}",
                file=sys.stderr,
            )
            return 1

    for name, spec in specs.items():
        print(f"{HIGHLIGHT_PREFIX} sources: {name}", flush=True)
        ok, out, err = run_cmd(["spectool", "-g", "-R", str(spec)], cwd=ROOT)
        print(out, end="")
        print(err, end="", file=sys.stderr)
        if not ok:
            print(
                f"{HIGHLIGHT_PREFIX} ✗ sources: {name} - spectool failed",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
