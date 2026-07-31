"""COPR (Fedora Copr) build service utilities.

Provides functions for:
- Credentials verification
- Build ID parsing from copr-cli output
- Repository slug validation
- Build status polling
- Fetching per-chroot builder logs after a failed build
"""

import gzip
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from lib import build_db
from lib.paths import get_package_log_dir
from lib.subprocess_utils import run_cmd

COPR_BUILD_URL = "https://copr.fedorainfracloud.org/coprs/build/{}/"
COPR_API_CHROOTS = (
    "https://copr.fedorainfracloud.org/api_3/build-chroot/list?build_id={}"
)
TERMINAL_STATES = {"success", "failed"}
CHROOT_LOG_CANDIDATES = ("builder-live.log.gz", "build.log.gz")


def parse_build_id(output: str) -> int | None:
    """Extract build ID from copr-cli build output.

    Searches for "Created builds:" line and extracts the integer ID.

    Args:
        output: stdout from 'copr-cli build' command

    Returns:
        Build ID as int, or None if not found
    """
    for line in output.splitlines():
        if "Created builds:" in line:
            try:
                return int(line.split()[-1])
            except (ValueError, IndexError):
                pass
    return None


def check_copr_credentials() -> bool:
    """Verify COPR credentials are valid using copr-cli whoami.

    Prints helpful error messages on failure.

    Returns:
        True if credentials are valid, False otherwise
    """
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


def validate_copr_repo(copr_repo: str) -> bool:
    """Validate COPR repository slug format.

    Expected format: owner/repo (e.g., nett00n/hyprland)

    Args:
        copr_repo: Repository slug to validate

    Returns:
        True if format is valid, False otherwise
    """
    return bool(re.match(r"^[\w-]+/[\w.-]+$", copr_repo))


def get_build_chroots(build_id: int) -> list[dict]:
    """Fetch per-chroot build results from the Copr API.

    Args:
        build_id: Copr build ID

    Returns:
        List of dicts with keys "name", "state", "result_url" (one per
        chroot the build targeted). Empty list on any network/parse failure.
    """
    url = COPR_API_CHROOTS.format(build_id)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return list(data.get("items", []))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return []


def download_chroot_log(result_url: str, dest: Path) -> bool:
    """Download and decompress a chroot's builder log to `dest`.

    Tries builder-live.log.gz first, falls back to build.log.gz.

    Args:
        result_url: Chroot result_url from get_build_chroots() (trailing slash)
        dest: Local path to write the decompressed log to

    Returns:
        True on success, False if no log could be fetched.
    """
    base = result_url if result_url.endswith("/") else result_url + "/"
    for name in CHROOT_LOG_CANDIDATES:
        try:
            with urllib.request.urlopen(base + name, timeout=30) as resp:
                content = gzip.decompress(resp.read())
        except (urllib.error.URLError, OSError, gzip.BadGzipFile):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return True
    return False


def fetch_failed_chroot_logs(pkg: str, build_id: int) -> None:
    """On a failed Copr build, download logs for the chroots that failed.

    Writes `<pkg-log-dir>/31-copr-<chroot>.log` for each failed chroot and a
    `<pkg-log-dir>/30-copr-chroots.log` summary (one line per chroot: name,
    state, result_url) so log-analysis can flag "failed on X only, Y
    succeeded" without another network round-trip. Best-effort: never raises.
    """
    try:
        chroots = get_build_chroots(build_id)
        if not chroots:
            return
        pkg_log_dir = get_package_log_dir(pkg)
        pkg_log_dir.mkdir(parents=True, exist_ok=True)
        summary_lines = [
            f"{c.get('name')} {c.get('state')} {c.get('result_url')}" for c in chroots
        ]
        (pkg_log_dir / "30-copr-chroots.log").write_text(
            "\n".join(summary_lines) + "\n"
        )
        for chroot in chroots:
            if chroot.get("state") != "failed":
                continue
            name = chroot.get("name")
            result_url = chroot.get("result_url")
            if not name or not result_url:
                continue
            download_chroot_log(result_url, pkg_log_dir / f"31-copr-{name}.log")
    except Exception:
        # Best-effort: never let log fetching break the polling/build flow.
        return


def poll_copr_status(target: str, packages_list: list[str]) -> bool:
    """Poll COPR status for packages with non-terminal states using copr-cli.

    Queries the status of pending builds and updates their state in
    build-report.db (touching only the `state` column -- see
    build_db.update_state). Skips packages that don't have a build_id or are
    already in terminal states (success/failed).

    Args:
        target: build_db target key (mock chroot) to read/write copr rows for
        packages_list: List of package names to check

    Returns:
        True if any status was updated, False otherwise
    """
    updated = False

    for pkg in packages_list:
        entry = build_db.get_stage(pkg, "copr", target) or {}
        build_id = entry.get("build_id")
        state = entry.get("state")

        # Only poll if we have a build_id and the state is not terminal
        if not build_id or state in TERMINAL_STATES:
            continue

        # Query copr-cli status
        ok, stdout, _ = run_cmd(["copr-cli", "status", str(build_id)])
        if not ok:
            continue

        # Parse output to get state (status command outputs "succeeded" or "failed" etc)
        new_state = None
        for line in stdout.splitlines():
            line_lower = line.lower()
            if "succeeded" in line_lower:
                new_state = "success"
                break
            elif "failed" in line_lower:
                new_state = "failed"
                break

        # Update if status changed
        if new_state and new_state != state:
            build_db.update_state(pkg, "copr", target, new_state)
            if new_state == "failed":
                fetch_failed_chroot_logs(pkg, build_id)
            updated = True

    return updated
