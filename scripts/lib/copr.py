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
from lib.deps import build_dep_graph, reverse_graph, transitive_deps
from lib.paths import ARCH, get_package_log_dir, mock_chroot
from lib.subprocess_utils import run_cmd
from lib.yaml_utils import SUPPORTED_FEDORA_VERSIONS

COPR_BUILD_URL = "https://copr.fedorainfracloud.org/coprs/build/{}/"
COPR_API_CHROOTS = (
    "https://copr.fedorainfracloud.org/api_3/build-chroot/list?build_id={}"
)
COPR_API_PROJECT = (
    "https://copr.fedorainfracloud.org/api_3/project?ownername={}&projectname={}"
)
TERMINAL_STATES = {"success", "failed"}
CHROOT_LOG_CANDIDATES = ("builder-live.log.gz", "build.log.gz")

# Every state copr-cli's `status` command can print (see copr_cli.helpers.
# colorize_status upstream). Matched as whole tokens, case-insensitively, and
# the *rightmost* match in the output wins -- see poll_copr_status().
_COPR_STATE_RE = re.compile(
    r"\b(succeeded|failed|canceled|skipped|forked|"
    r"running|starting|pending|importing|waiting)\b"
)

# Maps copr-cli's terminal states onto our own two-value state vocabulary.
# canceled/skipped/forked are terminal -- the build will never resolve itself
# -- so they're treated the same as a real failure: is_cached() only trusts
# "success", so anything else naturally gets resubmitted the next run (see
# docs/bugs.md BUG-0002). running/starting/pending/importing/waiting are
# intentionally absent: they're non-terminal, so the row is left alone and
# polled again next time.
_COPR_TERMINAL_STATE_MAP = {
    "succeeded": "success",
    "failed": "failed",
    "canceled": "failed",
    "skipped": "failed",
    "forked": "failed",
}

# Verdicts for chroot_coverage(): "verified"/"failed" come from a real local mock
# row; "unbuilt" is a same-arch chroot nobody has tried locally yet; "skipped" is
# a deliberate opt-out (packages.yaml's fedora: '<ver>': skip: true, see
# docs/packaging.md "Per-Fedora-version spec differences") and, like "verified",
# must never block a submission; "unverifiable" is a different-arch chroot
# (aarch64) mock can never build here -- see docs/todo.md TODO-0024.
COVERAGE_VERIFIED = "verified"
COVERAGE_FAILED = "failed"
COVERAGE_UNBUILT = "unbuilt"
COVERAGE_SKIPPED = "skipped"
COVERAGE_UNVERIFIABLE = "unverifiable"


def local_chroots() -> set[str]:
    """Every chroot this host can actually mock-build: one x86_64 chroot per
    SUPPORTED_FEDORA_VERSIONS. A Copr chroot outside this set (aarch64, or a
    Fedora version no longer in SUPPORTED_FEDORA_VERSIONS) can never have a
    local mock row -- see chroot_coverage()'s docstring for why that must
    never gate a submission.
    """
    return {mock_chroot(v) for v in SUPPORTED_FEDORA_VERSIONS}


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


def preflight(copr_repo: str) -> bool:
    """Validate a Copr repo slug and the local credentials before any build work.

    Prints the reason on failure; callers exit 2. Assumes copr_repo is non-empty --
    an unset COPR_REPO is fatal in stage-copr.py but means "skip the copr stage" in
    full-cycle.py, so that check stays at the call sites, not here.

    Args:
        copr_repo: Repository slug to validate

    Returns:
        True if the slug is well-formed and credentials are valid, False otherwise
    """
    if not validate_copr_repo(copr_repo):
        print(f"error: Invalid COPR_REPO format: {copr_repo}", file=sys.stderr)
        return False
    return check_copr_credentials()


def get_project_chroots(copr_repo: str) -> list[str]:
    """Fetch the list of chroot names a Copr project builds (e.g. every chroot
    enabled for `nett00n/hyprland`: fedora-43/44/rawhide x x86_64/aarch64).

    Args:
        copr_repo: Repository slug "owner/project"

    Returns:
        Sorted list of chroot names, or [] on any network/parse failure or an
        invalid slug -- callers must have their own fallback (see
        chroot_coverage()'s caller in stage-copr.py, which falls back to the
        x86_64 chroots derived from SUPPORTED_FEDORA_VERSIONS).
    """
    if not validate_copr_repo(copr_repo):
        return []
    ownername, projectname = copr_repo.split("/", 1)
    url = COPR_API_PROJECT.format(ownername, projectname)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return []
    # Live API returns chroot_repos as a dict keyed by chroot name; tolerate a
    # "chroots" list too in case that ever becomes the shape instead.
    chroot_repos = data.get("chroot_repos")
    if isinstance(chroot_repos, dict):
        return sorted(chroot_repos)
    chroots = data.get("chroots")
    if isinstance(chroots, list):
        return sorted(chroots)
    return []


def chroot_coverage(pkg: str, chroots: list[str]) -> dict[str, str]:
    """Score each Copr chroot against this package's local mock history.

    `build_db`'s `target` key IS the mock chroot name (see
    lib.paths.resolve_target), so this is a direct per-chroot stage lookup --
    no chroot-name translation needed.

    Returns {chroot: verdict}, verdict one of COVERAGE_VERIFIED/_FAILED/
    _UNBUILT/_SKIPPED/_UNVERIFIABLE (see the module-level constants' docstring).

    A chroot outside `local_chroots()` -- aarch64 (mock can't cross-build here,
    TODO-0024), or an x86_64 chroot for a Fedora version this host's
    SUPPORTED_FEDORA_VERSIONS no longer builds (e.g. a Copr project still
    listing a since-dropped chroot) -- is UNVERIFIABLE either way: there is no
    local mock row that could ever satisfy it, so it must never gate a
    submission. Without this, a stale Copr-side chroot would score every
    package UNBUILT forever and permanently block submission.
    """
    buildable = local_chroots()
    coverage: dict[str, str] = {}
    for chroot in chroots:
        if chroot not in buildable:
            coverage[chroot] = COVERAGE_UNVERIFIABLE
            continue
        entry = build_db.get_stage(pkg, "mock", chroot)
        state = entry.get("state") if entry else None
        reason = entry.get("reason") if entry else None
        if state == "success":
            coverage[chroot] = COVERAGE_VERIFIED
        elif state == "failed":
            coverage[chroot] = COVERAGE_FAILED
        elif state == "skipped" and reason == "config: skip":
            coverage[chroot] = COVERAGE_SKIPPED
        else:
            coverage[chroot] = COVERAGE_UNBUILT
    return coverage


def _project_chroots(copr_repo: str) -> tuple[list[str], bool]:
    """Return (chroots, used_fallback) for `copr_repo` -- the live Copr API list,
    or a same-arch fallback derived from SUPPORTED_FEDORA_VERSIONS if the API
    couldn't be reached."""
    chroots = get_project_chroots(copr_repo)
    if chroots:
        return chroots, False
    return sorted(f"fedora-{v}-{ARCH}" for v in SUPPORTED_FEDORA_VERSIONS), True


def _coverage_by_chroot(
    chroots: list[str], packages: dict
) -> dict[str, dict[str, int]]:
    """Tally each verdict (see chroot_coverage()) per chroot, across `packages`."""
    by_chroot: dict[str, dict[str, int]] = {
        chroot: {
            COVERAGE_VERIFIED: 0,
            COVERAGE_FAILED: 0,
            COVERAGE_UNBUILT: 0,
            COVERAGE_SKIPPED: 0,
            COVERAGE_UNVERIFIABLE: 0,
        }
        for chroot in chroots
    }
    for pkg in packages:
        verdicts = chroot_coverage(pkg, chroots)
        for chroot, verdict in verdicts.items():
            by_chroot[chroot][verdict] += 1
    return by_chroot


def blackout_chroots(copr_repo: str, packages: dict) -> list[str]:
    """Return locally-buildable chroots with zero verified/skipped packages.

    A chroot in this list will hold back *every* package in `packages` via
    `ineligible_packages()` -- not one straggler, all of them. That's the
    signal `stage-copr.py` uses to fail loud instead of silently submitting
    nothing (see docs/bugs.md BUG-0051). A chroot outside `local_chroots()`
    (aarch64, or unsupported here) never counts -- there's no local way to
    close that gap, so it must never be treated as a blackout.
    """
    if not packages:
        return []
    chroots, _ = _project_chroots(copr_repo)
    by_chroot = _coverage_by_chroot(chroots, packages)
    return [
        chroot
        for chroot, counts in by_chroot.items()
        if not counts[COVERAGE_UNVERIFIABLE]
        and not counts[COVERAGE_VERIFIED]
        and not counts[COVERAGE_SKIPPED]
    ]


def print_chroot_coverage(copr_repo: str, packages: dict) -> bool:
    """Print a per-chroot local-mock coverage table before a Copr submission.

    For each Copr chroot, reports how many of `packages` are verified (local
    mock succeeded), failed, unbuilt (never tried locally), skipped
    (deliberate opt-out), or unverifiable (not in `local_chroots()` -- aarch64,
    or a Fedora version this host's SUPPORTED_FEDORA_VERSIONS no longer
    builds, see docs/todo.md TODO-0024).

    Returns False only if some locally-buildable chroot has any package that
    is failed or unbuilt -- i.e. something `make full-cycle-matrix` could
    still catch locally before submission. An all-unverifiable gap never
    returns False: there is currently no way to close it locally, so it can't
    be a gate.
    """
    chroots, fallback_used = _project_chroots(copr_repo)

    print("\n=== Copr chroot coverage (local mock) ===")
    if fallback_used:
        print(
            "  (could not reach Copr API for chroot list -- falling back to "
            f"{ARCH} chroots derived from SUPPORTED_FEDORA_VERSIONS; "
            "aarch64 chroots are not represented here)"
        )

    by_chroot = _coverage_by_chroot(chroots, packages)

    ok = True
    blackout = False
    for chroot in chroots:
        counts = by_chroot[chroot]
        if counts[COVERAGE_UNVERIFIABLE]:
            note = (
                "not verifiable locally (aarch64, or unsupported here, see TODO-0024)"
            )
        else:
            note = (
                f"{counts[COVERAGE_VERIFIED]} verified, "
                f"{counts[COVERAGE_FAILED]} failed, "
                f"{counts[COVERAGE_UNBUILT]} unbuilt, "
                f"{counts[COVERAGE_SKIPPED]} skipped"
            )
            if counts[COVERAGE_FAILED] or counts[COVERAGE_UNBUILT]:
                ok = False
            if (
                packages
                and not counts[COVERAGE_VERIFIED]
                and not counts[COVERAGE_SKIPPED]
            ):
                note += " -- !! zero local coverage, every package will be held back"
                blackout = True
        print(f"  {chroot}: {note}")

    if blackout:
        print(
            "  -> at least one chroot has zero verified/skipped packages -- this "
            "run will submit nothing on it. Run `make matrix-chroot-<version>` to "
            "backfill coverage before the next nightly."
        )
    elif not ok:
        print(
            "  -> some chroots have no verified local mock build. "
            "Run `make full-cycle-matrix` to cover them before submitting, "
            "or set REQUIRE_CHROOT_COVERAGE=true to block instead of warn."
        )
    return ok


def ineligible_packages(copr_repo: str, packages: dict) -> dict[str, str]:
    """Return {package: reason} for packages not yet clear to submit to Copr.

    A package is eligible once every chroot in `local_chroots()` that this
    Copr project actually builds is COVERAGE_VERIFIED or COVERAGE_SKIPPED --
    i.e. it built cleanly (or was deliberately skipped) on every supported
    Fedora version this host can mock-build. A Copr chroot outside
    `local_chroots()` (aarch64, or a Fedora version this host's
    SUPPORTED_FEDORA_VERSIONS no longer builds) never blocks -- see
    chroot_coverage()'s docstring for why.
    """
    chroots, _ = _project_chroots(copr_repo)
    reasons: dict[str, str] = {}
    for pkg in packages:
        verdicts = chroot_coverage(pkg, chroots)
        bad = sorted(
            chroot
            for chroot, verdict in verdicts.items()
            if verdict
            not in (COVERAGE_VERIFIED, COVERAGE_SKIPPED, COVERAGE_UNVERIFIABLE)
        )
        if bad:
            reasons[pkg] = f"not verified on: {', '.join(bad)}"
    return reasons


def mock_failed_packages(packages: dict, target: str) -> list[str]:
    """Return names of packages whose mock stage ended this run in a "failed" state.

    Used as the basis for gating Copr submission (see copr_blocked_packages()):
    per-package pipelines used to submit each package to Copr as soon as its
    own mock succeeded, so a healthy early package (e.g. hyprutils) could
    already be public on Copr by the time a later, dependent package (e.g.
    Hyprland) failed mock -- publishing a dependency set that doesn't
    actually work together. See docs/bugs.md / issue #8.
    """
    return sorted(
        pkg
        for pkg in packages
        if (build_db.get_stage(pkg, "mock", target) or {}).get("state") == "failed"
    )


def block_transitive_dependents(
    names: list[str], packages: dict, all_packages: dict
) -> dict[str, list[str]]:
    """Map each package that must be held back -> the name(s) in `names`
    responsible (a name maps to itself).

    Scope is pure dependency-graph membership: `names` plus their transitive
    dependents (packages that consume their RPM), not their own dependencies
    (already published, unaffected) and not unrelated packages. Never
    special-cased on whether a dependent's own state happened to look fine --
    it may have built against a stale, already-published copy of a `names`
    ancestor. See docs/todo.md TODO-0084.

    Graph is built over `all_packages` (not the filtered `packages`) so
    dependents resolve correctly on a PACKAGE=-filtered run; the result is
    still restricted to packages actually in `packages`. The shared primitive
    behind copr_blocked_packages() (one failed target) and stage-copr.py's
    main() (every package ineligible_packages() marks not clear across the
    whole matrix, not just one target).
    """
    if not names:
        return {}
    dependents = reverse_graph(build_dep_graph(all_packages))
    blocked: dict[str, list[str]] = {}
    for name in names:
        blocked.setdefault(name, []).append(name)
        for dependent in transitive_deps(name, dependents):
            if dependent in packages:
                blocked.setdefault(dependent, []).append(name)
    return blocked


def copr_blocked_packages(
    packages: dict, all_packages: dict, target: str
) -> dict[str, list[str]]:
    """Map each package that must not be submitted to Copr this run -> the
    failed package(s) responsible (a failed package maps to itself).

    Scope is `target`'s mock failures plus their transitive dependents (see
    block_transitive_dependents()). Used by `full-cycle.py`, where `target` is
    the one chroot that invocation just built, so a single-target mock-failure
    check is exactly right. `stage-copr.py`'s main() -- the standalone
    submission `full-cycle-matrix` uses, spanning every chroot in the matrix,
    not one target -- calls block_transitive_dependents() directly over
    ineligible_packages()'s result instead of this function; see its
    docstring.
    """
    return block_transitive_dependents(
        mock_failed_packages(packages, target), packages, all_packages
    )


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

        # copr-cli status prints a single state token (see _COPR_STATE_RE).
        # Match whole tokens and take the rightmost one, so a stray earlier
        # mention of another state's name can't win by appearing first.
        matches = _COPR_STATE_RE.findall(stdout.lower())
        copr_state = matches[-1] if matches else None
        if copr_state is None:
            if stdout.strip():
                print(
                    f"warning: copr-cli status {build_id} returned an "
                    f"unrecognized state, leaving {pkg}/{target} as {state!r}: "
                    f"{stdout.strip()!r}",
                    file=sys.stderr,
                )
            continue
        new_state = _COPR_TERMINAL_STATE_MAP.get(copr_state)

        # Update if status changed
        if new_state and new_state != state:
            build_db.update_state(pkg, "copr", target, new_state)
            if new_state == "failed":
                fetch_failed_chroot_logs(pkg, build_id)
            updated = True

    return updated
