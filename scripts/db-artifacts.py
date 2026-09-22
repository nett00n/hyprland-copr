#!/usr/bin/env python3
"""Report and reclaim disk space tracked in build-report.db's artifacts table.

Recorded paths are absolute *container* paths (SRPMs/per-target vendor tarballs
under /root/rpmbuild -- a podman named volume, RPMs/logs/the vendor store under
/work -- the repo's own bind mount). Run inside the rpm toolbox container, those
resolve directly; run on the host, `lib.paths.host_path()` resolves the /work-
mounted realms back to their real location (#COPR-0015, #BUG-0062) -- the
rpmbuild-volume realm has no host path at all and is reported as such rather
than as "missing".

Usage:
  db-artifacts.py --usage [--verify]
  db-artifacts.py --prune [--confirm]
  db-artifacts.py --reset
  db-artifacts.py --forget PACKAGE
  db-artifacts.py --forget-repo TARGET
  db-artifacts.py --export [--format yaml|json] [--output PATH]
  db-artifacts.py --export-docs [--format yaml|json] [--output PATH]
"""

import argparse
import json
import shutil
import sys
from functools import cmp_to_key
from pathlib import Path
from typing import Any

from lib import build_db
from lib.paths import host_path
from lib.version import compare_evr
from lib.yaml_utils import dump_yaml_pretty

# Artifacts that accumulate one-per-build and are safe to prune down to the
# latest. Logs are deliberately excluded -- `make clean-logs` / --reset is
# the tool for those, not NVR/recency-based pruning (see docs/TODO.md).
_PRUNABLE_KINDS = {"srpm", "rpm", "vendor"}


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def _resolve_path(row: dict) -> Path | None:
    """Resolve an artifacts row's path against wherever this process runs.

    #COPR-0015, #BUG-0062. Tries the recorded (container-absolute) path first
    -- correct when actually running inside the container -- then falls back
    to `lib.paths.host_path()` for the repo/vendor-store realms. Returns None
    if neither resolves: either the file is genuinely gone, or (rpmbuild-
    volume) there was never a host path to try.
    """
    raw = Path(row["path"])
    if raw.exists():
        return raw
    resolved = host_path(row["realm"], row["path"])
    return resolved if resolved and resolved.exists() else None


def usage_report(verify: bool = False) -> None:
    """Print bytes used by (package, target), a grand total, and flag rows
    whose file is missing on disk (or, for rpmbuild-volume rows viewed from
    the host, not resolvable at all -- see `_resolve_path()`).

    `verify=True` (#COPR-0015, #BUG-0061) additionally re-hashes every row
    that has a recorded sha256 and flags a mismatch as corruption -- opt-in
    since it re-reads every artifact's full content, unlike the free
    missing-file check above.
    """
    rows = build_db.artifacts()
    if not rows:
        print("No artifacts recorded.")
        return

    totals: dict[tuple[str, str], int] = {}
    missing = 0
    unresolvable = 0
    corrupted: list[str] = []
    unverifiable = 0
    grand_total = 0
    for row in rows:
        size = row.get("size_bytes") or 0
        key = (row["package"], row["target"])
        totals[key] = totals.get(key, 0) + size
        grand_total += size
        resolved = _resolve_path(row)
        if resolved is None:
            if row["realm"] == "rpmbuild-volume":
                unresolvable += 1
            else:
                missing += 1
        elif verify:
            ok = build_db.verify_artifact(row["realm"], row["path"], resolved)
            if ok is False:
                corrupted.append(row["path"])
            elif ok is None:
                unverifiable += 1

    pkg_w = max(len(pkg) for pkg, _ in totals) + 2
    header = f"{'package':<{pkg_w}}{'target':<20}{'size':>10}"
    print(header)
    print("-" * len(header))
    for (pkg, target), size in sorted(totals.items()):
        print(f"{pkg:<{pkg_w}}{target:<20}{_human_size(size):>10}")
    print("-" * len(header))
    print(f"{'TOTAL':<{pkg_w}}{'':<20}{_human_size(grand_total):>10}")
    if missing:
        print(f"\n{missing} artifact row(s): file missing on disk")
    if unresolvable:
        print(
            f"\n{unresolvable} artifact row(s) in rpmbuild-volume: no host path "
            "exists for this realm -- run inside the container to check them"
        )
    if verify:
        if corrupted:
            print(
                f"\n{len(corrupted)} artifact(s): sha256 mismatch (corrupted on disk):"
            )
            for path in corrupted:
                print(f"  {path}")
        if unverifiable:
            print(f"\n{unverifiable} artifact(s): no sha256 recorded, not verifiable")


_EvrKey = cmp_to_key(compare_evr)


def _prune_key(row: dict) -> tuple[Any, int]:
    """Sort key for prune(): highest RPM version-release wins, mtime breaks
    ties (and is the whole comparison for unversioned rows, since compare_evr
    treats None/empty as equal to any other None/empty).
    """
    return (_EvrKey(row.get("version")), row.get("mtime") or 0)


def prune(confirm: bool) -> None:
    """Keep only the highest-version recorded artifact per (package, target,
    kind) among prunable kinds (srpm, rpm, vendor); delete the rest.

    "Highest version" compares the recorded artifacts.version column (the
    version-release-dist label lib.version.nvr() wrote) via
    lib.version.compare_evr() -- a real RPM version comparison, not
    wall-clock order, so a rebuild that lands on disk later but is an older
    version (a pin rollback, a corrected pinned-version) doesn't get kept
    over a genuinely newer one (docs/CHANGELOG.md 2026-09-08, closes the
    former docs/BUGS.md BUG-0017). Recorded mtime is only the tiebreaker,
    for equal or unversioned rows -- find_srpm() (`stage-srpm.py`) still
    picks its build input by mtime alone, a separate, smaller-blast-radius
    gap.

    Dry-run by default (confirm=False): prints what would be removed.
    """
    rows = [r for r in build_db.artifacts() if r["kind"] in _PRUNABLE_KINDS]
    by_key: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (row["package"], row["target"], row["kind"])
        by_key.setdefault(key, []).append(row)

    reclaimed = 0
    removed = 0
    for entries in by_key.values():
        if len(entries) < 2:
            continue
        entries.sort(key=_prune_key)
        for stale in entries[:-1]:  # highest version (then mtime) is last, kept
            size = stale.get("size_bytes") or 0
            action = "removing" if confirm else "would remove"
            print(f"  {action}: {stale['path']} ({_human_size(size)})")
            if confirm:
                # #BUG-0062: on the host, the recorded (container-absolute)
                # path won't exist -- fall back to its host-resolved location.
                # Neither existing (already gone, or rpmbuild-volume viewed
                # from the host) just means there's nothing to unlink; the
                # ledger row is still dropped below.
                path = _resolve_path(stale) or Path(stale["path"])
                if stale["realm"] == "vendor-store":
                    # The whole <pkg>/<input-hash>/ entry (tarball + meta.json)
                    # is store-owned; nothing else references it.
                    shutil.rmtree(path.parent, ignore_errors=True)
                elif path.exists():
                    path.unlink()
                build_db.delete_artifact(stale["realm"], stale["path"])
            reclaimed += size
            removed += 1

    if removed == 0:
        print("Nothing to prune.")
        return
    verb = "Removed" if confirm else "Would remove"
    print(f"\n{verb} {removed} artifact(s), {_human_size(reclaimed)}")
    if not confirm:
        print("Re-run with --confirm to actually delete.")


def _write_snapshot(snapshot: dict, fmt: str, output: str | None) -> None:
    text = (
        dump_yaml_pretty(snapshot)
        if fmt == "yaml"
        else json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    )
    if output:
        Path(output).write_text(text)
        print(f"Wrote {output}")
    else:
        print(text, end="")


def export_snapshot(fmt: str, output: str | None) -> None:
    """#COPR-0015, #BUG-0060: dump every table (runs, stage_results,
    stage_history, artifacts) to a deterministic yaml/json snapshot, for
    offline diffing. Unbounded (accumulates with every run) -- not meant to
    be committed; see export_docs_snapshot() for that.

    Prints to stdout by default; `output` writes to a file instead.
    """
    _write_snapshot(build_db.export_snapshot(), fmt, output)


def export_docs_snapshot(fmt: str, output: str | None) -> None:
    """#BUG-0031 (see COPR-0012): dump just the latest run per target plus
    stage_results -- what `gen-report.py --db-snapshot` needs to re-render
    the docs body without build-report.db (gitignored) or a Copr poll. Two
    exports of an unchanged db are byte-identical, so `make check-docs-drift`
    can diff a freshly regenerated snapshot against the committed one.

    Prints to stdout by default; `output` writes to a file instead.
    """
    _write_snapshot(build_db.export_docs_snapshot(), fmt, output)


def reset() -> None:
    """Clear stage_results and runs; keep the artifact ledger intact.

    Used by `make clean-logs`. Dropping `artifacts` here would orphan every
    tracked file on disk with no record of what it is or how to find it
    again (see docs/BUGS.md).
    """
    build_db.reset()
    print("Cleared stage_results and runs (artifacts preserved).")


def forget(package: str) -> None:
    """Remove all stage rows and artifact rows for a package (all targets).

    Does not unlink files from disk -- pair with --prune, or delete
    manually, if the package's files should go too.
    """
    build_db.forget_package(package)
    print(f"Forgot {package} (stage rows and artifact rows across all targets).")


def forget_repo(target: str) -> None:
    """Remove local-repo RPM artifact rows for one target (all packages).

    Used by `make clean-localrepo` after `rm -rf local-repo/<target>/`, so
    the ledger doesn't keep reporting files that directory deletion already
    removed. Does not touch other targets, other kinds (e.g. mock_log), or
    other realms (e.g. rpmbuild-volume srpms).
    """
    build_db.delete_artifacts_for_target(target, "repo", "rpm")
    print(f"Forgot local-repo RPM artifact rows for {target}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--usage", action="store_true", help="Report disk usage by package/target"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="With --usage, also re-hash every artifact with a recorded sha256 "
        "and flag corruption (re-reads full file content)",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove all but the highest-version artifact per (package, target, kind)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete during --prune (default: dry-run)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear stage_results and runs, keep the artifact ledger",
    )
    parser.add_argument(
        "--forget", metavar="PACKAGE", help="Remove all rows for PACKAGE"
    )
    parser.add_argument(
        "--forget-repo",
        metavar="TARGET",
        help="Remove local-repo RPM artifact rows for TARGET",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Dump runs/stage_results/stage_history/artifacts to a deterministic "
        "snapshot for offline diffing",
    )
    parser.add_argument(
        "--export-docs",
        action="store_true",
        help="#BUG-0031: dump just the latest run per target + stage_results -- "
        "the narrow, committable input to `gen-report.py --db-snapshot` / "
        "`make check-docs-drift`",
    )
    parser.add_argument(
        "--format",
        choices=("yaml", "json"),
        default="yaml",
        help="Format for --export (default: yaml)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="With --export, write to PATH instead of stdout",
    )
    args = parser.parse_args()

    if not any(
        [
            args.usage,
            args.prune,
            args.reset,
            args.forget,
            args.forget_repo,
            args.export,
            args.export_docs,
        ]
    ):
        parser.error(
            "one of --usage, --prune, --reset, --forget, --forget-repo, --export, "
            "--export-docs is required"
        )

    if args.usage:
        usage_report(verify=args.verify)
    if args.prune:
        prune(args.confirm)
    if args.reset:
        reset()
    if args.forget:
        forget(args.forget)
    if args.forget_repo:
        forget_repo(args.forget_repo)
    if args.export:
        export_snapshot(args.format, args.output)
    if args.export_docs:
        export_docs_snapshot(args.format, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
