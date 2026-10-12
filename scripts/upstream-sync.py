#!/usr/bin/env python3
"""Fetch every upstream mirror and check its worktree out at the default branch.

Usage:
    python3 scripts/upstream-sync.py              # all packages.yaml urls
    python3 scripts/upstream-sync.py --clean      # delete .cache/upstream first

Rebuilds the disposable cache under .cache/upstream/ (see
docs/features/COPR-0004-version-auto-bump.md); the mirrors are otherwise created on
demand by `make update-versions`. #COPR-0004
"""

import argparse
import shutil
import sys

from lib.config import env_int
from lib.paths import PACKAGES_YAML, UPSTREAM_DIR
from lib.upstream import UpstreamError, list_upstreams, sync_upstream
from lib.yaml_utils import get_packages
from concurrent.futures import ThreadPoolExecutor


def sync_all(packages: dict, jobs: int = 8) -> list[str]:
    """Sync every upstream in `packages`; return one error line per failure.

    #COPR-0004
    """
    modules = list_upstreams(packages)

    def _one(mod: dict) -> str | None:
        try:
            sync_upstream(mod["url"])
        except UpstreamError as exc:
            return f"{mod['name']}: {exc}"
        print(f"  synced {mod['name']}", file=sys.stderr)
        return None

    if jobs <= 1 or len(modules) <= 1:
        results = [_one(m) for m in modules]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(_one, modules))
    return sorted(r for r in results if r)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--clean", action="store_true", help="delete the whole cache first"
    )
    args = parser.parse_args()

    if args.clean and UPSTREAM_DIR.exists():
        shutil.rmtree(UPSTREAM_DIR)
        print(f"removed {UPSTREAM_DIR}", file=sys.stderr)

    if not PACKAGES_YAML.exists():
        print(f"error: {PACKAGES_YAML} not found", file=sys.stderr)
        sys.exit(1)

    errors = sync_all(get_packages(PACKAGES_YAML), env_int("UPDATE_VERSIONS_JOBS", 8))
    if errors:
        print(f"error: {len(errors)} upstream(s) failed to sync:", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)
    print(f"✓ upstream mirrors synced under {UPSTREAM_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
