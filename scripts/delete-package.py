#!/usr/bin/env python3
"""Remove a package and every place it's tracked: packages.yaml entry, group
membership in groups.yaml, its sources.lock.yaml entry, build-report.db rows,
every logs/runs/<run_id>/<target>/<name> directory still on disk
(case-insensitive lookup by name), its RPMs in local-repo/<target>/ (repo
metadata regenerated), and its files in the rpmbuild dir (SOURCES/SRPMS/RPMS).

Resolves the package primarily against packages.yaml. If it's already gone
from there (e.g. a previous run only got as far as popping the yaml entry),
falls back to a case-insensitive match against whatever leftover state
still names it, so this is also the tool for mopping up stragglers.

Usage:
    python3 scripts/delete-package.py <package>

Example:
    python3 scripts/delete-package.py waybar-git
"""

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import build_db, local_repo  # noqa: E402
from lib.paths import (  # noqa: E402
    GROUPS_YAML,
    PACKAGES_YAML,
    RUNS_LOG_DIR,
    iter_package_log_dirs,
)
from lib.source_lock import load_lock, save_lock  # noqa: E402
from lib.yaml_utils import (  # noqa: E402
    find_package_name,
    get_packages,
    load_groups_yaml,
    write_yaml_file,
)


def resolve_name(query: str, packages: dict, groups: dict, lock: dict) -> str | None:
    """Case-insensitive match for `query` against packages.yaml, then, if not
    found there, against every other store that might still name it."""
    pkg_name = find_package_name(packages, query)
    if pkg_name is not None:
        return pkg_name

    query_lower = query.lower()
    candidates: set[str] = set(lock)
    for group in groups.values():
        candidates.update(group.get("packages") or [])
    candidates.update(build_db.known_packages())
    if RUNS_LOG_DIR.exists():
        candidates.update(p.name for p in RUNS_LOG_DIR.glob("*/*/*") if p.is_dir())

    matches = {name for name in candidates if name.lower() == query_lower}
    if len(matches) == 1:
        return matches.pop()
    if len(matches) > 1:
        sys.exit(f"error: ambiguous package name {query!r}, matches: {sorted(matches)}")
    return None


RPMBUILD_DIR = Path.home() / "rpmbuild"


def sweep_rpmbuild(pkg: str, rpmbuild: Path = RPMBUILD_DIR) -> int:
    """#COPR-0013, #BUG-0070: remove `pkg`'s files from the rpmbuild dir
    (the rpmbuild podman volume, mounted at ~/rpmbuild). Returns how many
    entries were removed; no-op if the dir doesn't exist.

    SOURCES/ and SRPMS/ entries match `<pkg>-<digit>...`; built RPMs under
    RPMS/<arch>/ are matched by source package. A bare `<pkg>-*` glob would
    also take `<pkg>-protocols-*` and the like.
    """
    own_file = re.compile(rf"{re.escape(pkg)}-\d.*")
    removed = 0
    for sub in ("SOURCES", "SRPMS"):
        for entry in sorted((rpmbuild / sub).glob(f"{pkg}-*")):
            if not own_file.fullmatch(entry.name):
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed += 1
    for rpm_path in sorted((rpmbuild / "RPMS").glob("*/*.rpm")):
        if local_repo.rpm_source_name(rpm_path) == pkg:
            rpm_path.unlink()
            removed += 1
    return removed


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]
    packages = get_packages()
    groups = load_groups_yaml()
    lock = load_lock()

    pkg_name = resolve_name(query, packages, groups, lock)
    if pkg_name is None:
        sys.exit(f"error: unknown package: {query}")

    parts = []

    if pkg_name in packages:
        packages.pop(pkg_name)
        write_yaml_file(PACKAGES_YAML, packages)
        parts.append("packages.yaml")

    changed_groups = [
        group_name
        for group_name, group in groups.items()
        if pkg_name in (group.get("packages") or [])
    ]
    for group_name in changed_groups:
        groups[group_name]["packages"].remove(pkg_name)
    if changed_groups:
        write_yaml_file(GROUPS_YAML, groups)
        parts.append(f"groups.yaml ({', '.join(changed_groups)})")

    if pkg_name in lock:
        lock.pop(pkg_name)
        save_lock(lock)
        parts.append("sources.lock.yaml")

    if pkg_name in build_db.known_packages():
        build_db.forget_package(pkg_name)
        parts.append("build-report.db")

    log_dirs = iter_package_log_dirs(pkg_name)
    for log_dir in log_dirs:
        shutil.rmtree(log_dir)
    if log_dirs:
        parts.append(f"{len(log_dirs)} log dir(s) under logs/runs/")

    repo_removed = local_repo.remove_package_rpms(pkg_name)
    if repo_removed:
        parts.append(
            f"{sum(repo_removed.values())} RPM(s) in local-repo "
            f"({', '.join(repo_removed)})"
        )

    volume_removed = sweep_rpmbuild(pkg_name)
    if volume_removed:
        parts.append(f"{volume_removed} file(s) in rpmbuild volume")

    if not parts:
        sys.exit(f"error: {pkg_name} matched but nothing to remove (already clean)")

    print(f"Removed {pkg_name}: {', '.join(parts)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
