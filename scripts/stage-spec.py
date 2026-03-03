#!/usr/bin/env python3
"""Stage 1: Generate spec files for each package.

Reads packages.yaml, runs gen-spec.py per package, and records
success/failure in logs/build-status.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
"""

import os
import sys

from lib.paths import LOG_DIR, ROOT
from lib.reporting import status
from lib.version import nvr
from lib.yaml_utils import get_packages, load_build_status, save_build_status

PYTHON = sys.executable


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    package_filter = os.environ.get("PACKAGE", "")

    all_packages = get_packages()
    if package_filter:
        names = [n.strip() for n in package_filter.split(",") if n.strip()]
        unknown = [n for n in names if n not in all_packages]
        if unknown:
            sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
        packages = {n: all_packages[n] for n in names}
    else:
        packages = all_packages

    LOG_DIR.mkdir(exist_ok=True)
    build_status = load_build_status()
    build_status.setdefault("stages", {})["spec"] = {}

    failed = False
    print("\n=== spec ===")
    for pkg, meta in packages.items():
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        log = LOG_DIR / f"{pkg}-00-spec.log"
        log.unlink(missing_ok=True)

        import subprocess

        result = subprocess.run(
            [PYTHON, str(ROOT / "scripts" / "gen-spec.py"), pkg],
            capture_output=True,
            text=True,
        )
        with open(log, "w") as fh:
            if result.stdout:
                fh.write(result.stdout)
            if result.stderr:
                fh.write(result.stderr)
            fh.write(f"[exit: {result.returncode}]\n")

        ok = result.returncode == 0
        state = "success" if ok else "failed"
        if not ok:
            failed = True
        status("spec", pkg, "ok" if ok else "fail")

        entry: dict = {
            "state": state,
            "version": ver,
            "log": str(log.relative_to(ROOT)),
        }
        if "devel" in meta:
            entry["subpackages"] = {"devel": {"state": state, "version": ver}}
        build_status["stages"]["spec"][pkg] = entry

    save_build_status(build_status)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
