#!/usr/bin/env python3
"""Stage 1: Generate spec files for each package.

Reads packages.yaml, runs gen-spec.py per package, and records
success/failure in build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
"""

import os
import subprocess
import sys

from lib.paths import ROOT, get_package_log_dir
from lib.reporting import status
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    init_stage,
    save_build_status,
)

PYTHON = sys.executable


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")

    packages, build_status = init_stage("spec")

    failed = False
    print("\n=== spec ===")
    for pkg, meta in packages.items():
        meta = apply_os_overrides(meta, fedora_version)
        if meta.get("_skip"):
            print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
            build_status["stages"]["spec"][pkg] = {"state": "skipped", "version": None}
            continue
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        pkg_log_dir = get_package_log_dir(pkg)
        pkg_log_dir.mkdir(parents=True, exist_ok=True)
        log = pkg_log_dir / "00-spec.log"
        log.unlink(missing_ok=True)

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
