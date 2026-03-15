#!/usr/bin/env python3
"""Stage 4: Submit SRPMs to Copr and record build IDs.

Reads packages.yaml and build-report.yaml for srpm stage results.
Skips packages where srpm stage failed or COPR_REPO is not set.
Records build IDs in build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  COPR_REPO       Copr repo slug, e.g. nett00n/hyprland (required)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  PROCEED_BUILD   Skip packages where copr stage already succeeded
"""

import os
import re
import sys
from typing import Any

from lib.paths import ROOT, get_package_log_dir
from lib.reporting import status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    init_stage,
    now_epoch,
    save_build_status,
)


def parse_build_id(output: str) -> int | None:
    for line in output.splitlines():
        if "Created builds:" in line:
            try:
                return int(line.split()[-1])
            except (ValueError, IndexError):
                pass
    return None


def check_copr_credentials() -> bool:
    """Verify COPR credentials are valid."""
    ok, stdout, stderr = run_cmd(["copr-cli", "whoami"])
    if not ok:
        print("error: COPR credentials are invalid or missing", file=sys.stderr)
        print(
            "  Set up credentials at: https://copr.fedorainfracloud.org/api/",
            file=sys.stderr,
        )
        print("  Save to: ~/.config/copr/copr.conf", file=sys.stderr)
        if stderr:
            print(f"  Details: {stderr.strip()}", file=sys.stderr)
        return False
    return True


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    copr_repo = os.environ.get("COPR_REPO", "")

    if not copr_repo:
        print(
            "error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)",
            file=sys.stderr,
        )
        sys.exit(2)
    if not re.match(r"^[\w-]+/[\w.-]+$", copr_repo):
        print(f"error: Invalid COPR_REPO format: {copr_repo}", file=sys.stderr)
        sys.exit(2)

    # Check credentials early
    if not check_copr_credentials():
        sys.exit(2)

    packages, build_status = init_stage("copr")
    srpm_stage = build_status.get("stages", {}).get("srpm", {})
    mock_stage = build_status.get("stages", {}).get("mock", {})

    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"
    stages = build_status.get("stages", {})
    if not proceed:
        stages["copr"] = {}
    else:
        stages.setdefault("copr", {})

    failed = False
    print("\n=== copr ===")
    for pkg, meta in packages.items():
        meta = apply_os_overrides(meta, fedora_version)
        if meta.get("_skip"):
            print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
            build_status["stages"]["copr"][pkg] = {
                "state": "skipped",
                "version": None,
                "build_id": None,
                "log": None,
            }
            continue
        ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
        has_devel = "devel" in meta
        pkg_log_dir = get_package_log_dir(pkg)
        pkg_log_dir.mkdir(parents=True, exist_ok=True)
        log = pkg_log_dir / "30-copr.log"
        log.unlink(missing_ok=True)

        # Skip if copr stage already succeeded
        prior_copr_state = (
            build_status.get("stages", {}).get("copr", {}).get(pkg, {}).get("state")
        )
        if proceed and verbose_proceed_check("copr", pkg, prior_copr_state):
            status("copr", pkg, "skip", "already succeeded")
            continue

        srpm_state = srpm_stage.get(pkg, {}).get("state", "")
        srpm_path = srpm_stage.get(pkg, {}).get("path")
        mock_state = mock_stage.get(pkg, {}).get("state", "")

        if (
            srpm_state in ("failed", "skipped")
            or not srpm_path
            or mock_state in ("failed", "skipped")
        ):
            blocker = (
                f"mock {mock_state}"
                if mock_state in ("failed", "skipped")
                else f"srpm {srpm_state}"
            )
            status("copr", pkg, "skip", blocker)
            entry: dict[str, Any] = {
                "state": "skipped",
                "version": ver,
                "build_id": None,
                "log": None,
            }
            if has_devel:
                entry["subpackages"] = {"devel": {"state": "skipped", "version": ver}}
            build_status["stages"]["copr"][pkg] = entry
            continue

        ok, stdout, _ = run_cmd(["copr-cli", "build", copr_repo, srpm_path], log)
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
