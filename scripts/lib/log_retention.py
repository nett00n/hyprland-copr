"""#COPR-0022: retention policy for logs/runs/<run_id>/.

Each run gets its own directory (see lib.paths.get_run_log_dir), so unlike the
old flat `logs/build/<pkg>/` layout -- overwritten every run and therefore
self-bounding -- the run-scoped tree grows without limit unless something
prunes it. This module is that something: keep the newest N run dirs, drop
the rest. Nothing else under `logs/` (`logs/make`, `logs/.pipeline.lock`,
`logs/build-report.db.last`, ...) lives under `logs/runs`, so it is never a
candidate for removal here.
"""

import os
import shutil
from pathlib import Path

from lib.paths import RUNS_LOG_DIR

DEFAULT_RETENTION_RUNS = 10


def retention_from_env() -> int:
    """#COPR-0022: LOG_RETENTION_RUNS env var, falling back to the default.

    An unset or non-numeric value falls back rather than raising -- a typo'd
    env var shouldn't be able to turn a nightly build into a crash.
    """
    raw = os.environ.get("LOG_RETENTION_RUNS", "")
    if not raw:
        return DEFAULT_RETENTION_RUNS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_RUNS
    return value if value >= 1 else DEFAULT_RETENTION_RUNS


def list_run_dirs_newest_first() -> list[tuple[int, Path]]:
    """#COPR-0022: numeric run directories under logs/runs/, newest id first."""
    if not RUNS_LOG_DIR.exists():
        return []
    numbered = []
    for entry in RUNS_LOG_DIR.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            numbered.append((int(entry.name), entry))
    numbered.sort(key=lambda pair: pair[0], reverse=True)
    return numbered


def prune_run_logs(keep: int) -> list[int]:
    """#COPR-0022: remove all but the newest `keep` run directories.

    Non-numeric entries under `logs/runs/` (there shouldn't be any, but a
    stray `latest` symlink or similar is tolerated) are left alone. Returns
    the run ids that were removed, newest-first among the removed set is not
    guaranteed -- callers that care should sort.
    """
    if keep < 1:
        raise ValueError(f"keep must be >= 1, got {keep}")
    removed = []
    for run_id, path in list_run_dirs_newest_first()[keep:]:
        shutil.rmtree(path, ignore_errors=True)
        removed.append(run_id)
    return removed


def refresh_latest_link(run_id: int) -> None:
    """#COPR-0022: point `logs/runs/latest` at this run's directory.

    Best-effort convenience for a human poking around on disk -- nothing in
    the pipeline reads this symlink back. Silently no-ops if the run
    directory doesn't exist yet or symlinks aren't supported (e.g. some
    Windows configurations).
    """
    run_dir = RUNS_LOG_DIR / str(run_id)
    link = RUNS_LOG_DIR / "latest"
    if not run_dir.is_dir():
        return
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(run_dir.name, target_is_directory=True)
    except OSError:
        pass
