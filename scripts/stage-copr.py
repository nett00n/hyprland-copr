#!/usr/bin/env python3
"""Stage 4: Submit SRPMs to Copr and record build IDs.

Reads packages.yaml and logs/build-status.yaml for srpm stage results.
Skips packages where srpm stage failed or COPR_REPO is not set.
Records build IDs in build-status.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  COPR_REPO       Copr repo slug, e.g. nett00n/hyprland (required)
  PROCEED_BUILD   Skip packages where copr stage already succeeded
"""

import os
import sys

from lib.paths import LOG_DIR, ROOT
from lib.reporting import status
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import (
    filter_packages,
    get_packages,
    load_build_status,
    now_epoch,
    save_build_status,
    stage_was_success,
)


def parse_build_id(output: str) -> int | None:
    for line in output.splitlines():
        if "Created builds:" in line:
            try:
                return int(line.split()[-1])
            except (ValueError, IndexError):
                pass
    return None


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    copr_repo = os.environ.get("COPR_REPO", "")
    package_filter = os.environ.get("PACKAGE", "")

    if not copr_repo:
        print(
            "error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)",
            file=sys.stderr,
        )
        sys.exit(2)

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_filter)

    LOG_DIR.mkdir(exist_ok=True)
    build_status = load_build_status()
    srpm_stage = build_status.get("stages", {}).get("srpm", {})
    mock_stage = build_status.get("stages", {}).get("mock", {})

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    stages = build_status.setdefault("stages", {})
    if not proceed:
        stages["copr"] = {}
    stages.setdefault("copr", {})

    failed = False
    print("\n=== copr ===")
    for pkg, meta in packages.items():
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        has_devel = "devel" in meta
        log = LOG_DIR / f"{pkg}-30-copr.log"
        log.unlink(missing_ok=True)

        # Skip if copr stage already succeeded
        if proceed and stage_was_success(build_status, "copr", pkg):
            status("copr", pkg, "skip")
            continue

        srpm_state = srpm_stage.get(pkg, {}).get("state", "")
        srpm_path = srpm_stage.get(pkg, {}).get("path")
        mock_state = mock_stage.get(pkg, {}).get("state", "")

        if (
            srpm_state in ("failed", "skipped")
            or not srpm_path
            or mock_state in ("failed", "skipped")
        ):
            status("copr", pkg, "skip")
            entry = {"state": "skipped", "version": ver, "build_id": None, "log": None}
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "skipped", "version": ver}}
            build_status["stages"]["copr"][pkg] = entry
            continue

        ok, stdout, _ = run_cmd(f"copr-cli build {copr_repo} {srpm_path}", log)
        state = "success" if ok else "failed"
        if not ok:
            failed = True
        build_id = parse_build_id(stdout) if ok else None
        status("copr", pkg, "ok" if ok else "fail")

        entry = {
            "state": state,
            "version": ver,
            "build_id": build_id,
            "log": str(log.relative_to(ROOT)),
            **({"completed_at": now_epoch()} if ok else {}),
        }
        if has_devel:
            entry["subpackages"] = {"devel": {"state": state, "version": ver}}
        build_status["stages"]["copr"][pkg] = entry
        save_build_status(build_status)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
