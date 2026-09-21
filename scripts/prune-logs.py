#!/usr/bin/env python3
"""#COPR-0022: enforce the log-retention policy on logs/runs/.

Usage:
  prune-logs.py [--keep N] [--confirm]

Dry-run by default (prints what *would* be removed), same convention as
`make db-prune` -- pass --confirm to actually delete. KEEP defaults to
LOG_RETENTION_RUNS (env var, itself defaulting to 10).
"""

import argparse
import sys

from lib.log_retention import (
    list_run_dirs_newest_first,
    prune_run_logs,
    retention_from_env,
)
from lib.paths import LOG_DIR

HIGHLIGHT_PREFIX = "█▓▒░"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=retention_from_env())
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)

    if args.keep < 1:
        print(f"error: --keep must be >= 1, got {args.keep}", file=sys.stderr)
        return 1

    runs = list_run_dirs_newest_first()
    to_remove = runs[args.keep :]
    if not to_remove:
        print(
            f"{HIGHLIGHT_PREFIX} ✓ Nothing to prune ({len(runs)} run(s), keeping {args.keep})"
        )
        return 0

    verb = "removing" if args.confirm else "would remove"
    for _run_id, path in to_remove:
        print(f"  {verb}: {path.relative_to(LOG_DIR)}")

    if not args.confirm:
        print(
            f"{HIGHLIGHT_PREFIX} Dry-run: {len(to_remove)} run(s) would be removed "
            f"(of {len(runs)} total, keeping {args.keep}). Pass --confirm to delete."
        )
        return 0

    removed = prune_run_logs(args.keep)
    print(f"{HIGHLIGHT_PREFIX} ✓ Removed {len(removed)} run(s), kept {args.keep}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
