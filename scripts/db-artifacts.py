#!/usr/bin/env python3
"""Report and reclaim disk space tracked in build-report.db's artifacts table.

Must be run inside the rpm toolbox container: recorded paths are the same
absolute container paths used when the artifact was written (SRPMs/per-target
vendor tarballs under /root/rpmbuild, RPMs/logs/the vendor store under /work),
and only resolve correctly with the same volumes mounted.

Usage:
  db-artifacts.py --usage
  db-artifacts.py --prune [--confirm]
  db-artifacts.py --reset
  db-artifacts.py --forget PACKAGE
  db-artifacts.py --forget-repo TARGET
"""

import argparse
import shutil
from pathlib import Path

from lib import build_db

# Artifacts that accumulate one-per-build and are safe to prune down to the
# latest. Logs are deliberately excluded -- `make clean-logs` / --reset is
# the tool for those, not NVR/recency-based pruning (see docs/todo.md).
_PRUNABLE_KINDS = {"srpm", "rpm", "vendor"}


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def usage_report() -> None:
    """Print bytes used by (package, target), a grand total, and flag rows
    whose file is missing on disk.
    """
    rows = build_db.artifacts()
    if not rows:
        print("No artifacts recorded.")
        return

    totals: dict[tuple[str, str], int] = {}
    missing = 0
    grand_total = 0
    for row in rows:
        size = row.get("size_bytes") or 0
        key = (row["package"], row["target"])
        totals[key] = totals.get(key, 0) + size
        grand_total += size
        if not Path(row["path"]).exists():
            missing += 1

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


def prune(confirm: bool) -> None:
    """Keep only the most recently recorded artifact per (package, target,
    kind) among prunable kinds (srpm, rpm, vendor); delete the rest.

    "Most recent" is by recorded mtime, matching find_srpm()'s own
    newest-by-mtime convention elsewhere in the pipeline -- not a real NVR
    comparison (see docs/bugs.md for the existing mtime-vs-NVR caveat this
    inherits).

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
        entries.sort(key=lambda r: r.get("mtime") or 0)
        for stale in entries[:-1]:  # newest (highest mtime) is last, kept
            size = stale.get("size_bytes") or 0
            action = "removing" if confirm else "would remove"
            print(f"  {action}: {stale['path']} ({_human_size(size)})")
            if confirm:
                path = Path(stale["path"])
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


def reset() -> None:
    """Clear stage_results and runs; keep the artifact ledger intact.

    Used by `make clean-logs`. Dropping `artifacts` here would orphan every
    tracked file on disk with no record of what it is or how to find it
    again (see docs/bugs.md).
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
        "--prune",
        action="store_true",
        help="Remove all but the newest artifact per (package, target, kind)",
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
    args = parser.parse_args()

    if not any([args.usage, args.prune, args.reset, args.forget, args.forget_repo]):
        parser.error(
            "one of --usage, --prune, --reset, --forget, --forget-repo is required"
        )

    if args.usage:
        usage_report()
    if args.prune:
        prune(args.confirm)
    if args.reset:
        reset()
    if args.forget:
        forget(args.forget)
    if args.forget_repo:
        forget_repo(args.forget_repo)


if __name__ == "__main__":
    main()
