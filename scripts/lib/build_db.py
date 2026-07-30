"""SQLite storage for build-report data: run history, per-stage results, artifacts.

Replaces build-report.yaml. Schema key is `target` (the mock chroot triple, e.g.
`fedora-44-x86_64`), not `fedora_version` -- see docs/todo.md "Build matrix" for why.

See docs/todo.md "Build report db" for follow-ups (append-only attempt history,
artifact sha256, etc).
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import paths

STAGES = ["validate", "spec", "vendor", "srpm", "mock", "copr"]

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id             INTEGER PRIMARY KEY,
  started_at     INTEGER NOT NULL,
  completed_at   INTEGER,
  target         TEXT    NOT NULL,
  distro         TEXT    NOT NULL,
  distro_version TEXT    NOT NULL,
  arch           TEXT    NOT NULL,
  copr_repo      TEXT,
  package_filter TEXT,
  exit_state     TEXT
);

CREATE TABLE IF NOT EXISTS stage_results (
  package        TEXT    NOT NULL,
  stage          TEXT    NOT NULL,
  target         TEXT    NOT NULL,
  state          TEXT    NOT NULL,
  version        TEXT,
  reason         TEXT,
  log            TEXT,
  path           TEXT,
  build_id       INTEGER,
  errors         INTEGER,
  warnings       INTEGER,
  has_devel      INTEGER NOT NULL DEFAULT 0,
  force_run      INTEGER NOT NULL DEFAULT 0,
  started_at     INTEGER,
  completed_at   INTEGER,
  hashes_json    TEXT,
  run_id         INTEGER REFERENCES runs(id),
  updated_at     INTEGER NOT NULL,
  PRIMARY KEY (package, stage, target)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS artifacts (
  path           TEXT NOT NULL,
  realm          TEXT NOT NULL,
  kind           TEXT NOT NULL,
  package        TEXT NOT NULL,
  target         TEXT NOT NULL,
  version        TEXT,
  size_bytes     INTEGER,
  mtime          INTEGER,
  recorded_at    INTEGER NOT NULL,
  PRIMARY KEY (realm, path)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS artifacts_pkg  ON artifacts(package, target);
CREATE INDEX IF NOT EXISTS artifacts_kind ON artifacts(kind);
"""

_STAGE_ENTRY_COLUMNS = [
    "state",
    "version",
    "reason",
    "log",
    "path",
    "build_id",
    "errors",
    "warnings",
    "has_devel",
    "force_run",
    "started_at",
    "completed_at",
]

_conn: sqlite3.Connection | None = None
_conn_path: Path | None = None


def now_epoch() -> int:
    """Return current Unix timestamp as integer."""
    return int(time.time())


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Return a cached connection to the build DB, reconnecting if the path changed.

    Reads `paths.BUILD_DB` at call time (not at import/def time), so tests can
    monkeypatch it per-test and get an isolated database -- unlike the old
    `load_build_status(path=BUILD_STATUS_YAML)`, whose default bound at import.
    """
    global _conn, _conn_path
    target_path = path or paths.BUILD_DB
    if _conn is not None and _conn_path == target_path:
        return _conn
    close()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    _migrate(conn)
    _conn = conn
    _conn_path = target_path
    return conn


def close() -> None:
    """Close the cached connection, if any. Mainly for test teardown."""
    global _conn, _conn_path
    if _conn is not None:
        _conn.close()
    _conn = None
    _conn_path = None


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a row to a dict, dropping NULL columns.

    A SQL row always has every column; the yaml entries it replaces only ever
    had the keys that were actually set. `dict.get(k, default)` at ~15 call
    sites relies on that "absent key = missing" semantic -- a NULL surviving
    as `None` would silently defeat every one of those defaults.
    """
    return {k: v for k, v in dict(row).items() if v is not None}


def _stage_entry(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    entry = _row_dict(row)
    hashes_json = entry.pop("hashes_json", None)
    if hashes_json is not None:
        entry["hashes"] = json.loads(hashes_json)
    # Internal bookkeeping columns, not part of the entry shape consumers see.
    entry.pop("run_id", None)
    entry.pop("updated_at", None)
    entry.pop("package", None)
    entry.pop("stage", None)
    entry.pop("target", None)
    return entry


# --- runs ----------------------------------------------------------------


def start_run(
    target: str,
    distro: str,
    distro_version: str,
    arch: str,
    copr_repo: str = "",
    package_filter: str = "",
) -> int:
    """Insert a new run row and return its id."""
    conn = connect()
    cur = conn.execute(
        """
        INSERT INTO runs
            (started_at, target, distro, distro_version, arch, copr_repo, package_filter)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_epoch(),
            target,
            distro,
            distro_version,
            arch,
            copr_repo or None,
            package_filter or None,
        ),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def finish_run(run_id: int, exit_state: str) -> None:
    """Stamp a run's completed_at and exit_state."""
    conn = connect()
    conn.execute(
        "UPDATE runs SET completed_at = ?, exit_state = ? WHERE id = ?",
        (now_epoch(), exit_state, run_id),
    )
    conn.commit()


def latest_run(target: str) -> dict[str, Any] | None:
    """Return the most recent run row for `target`, or None if none exists yet.

    Mirrors the old `if not BUILD_STATUS_YAML.exists(): error; exit(1)` guard in
    gen-report.py -- callers should treat None the same way: report "no build
    recorded yet" rather than rendering a fabricated report.
    """
    conn = connect()
    row = conn.execute(
        "SELECT * FROM runs WHERE target = ? ORDER BY id DESC LIMIT 1",
        (target,),
    ).fetchone()
    return _row_dict(row) if row is not None else None


# --- stage_results ---------------------------------------------------------


def get_stage(package: str, stage: str, target: str) -> dict[str, Any] | None:
    """Return the stage entry dict for (package, stage, target), or None."""
    conn = connect()
    row = conn.execute(
        "SELECT * FROM stage_results WHERE package = ? AND stage = ? AND target = ?",
        (package, stage, target),
    ).fetchone()
    return _stage_entry(row)


def stage_map(
    target: str,
    stage: str | None = None,
    packages: list[str] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {stage: {package: entry}} for `target`, optionally filtered.

    Ordered by package name so callers get a deterministic iteration order
    (SQL row order is otherwise unspecified) -- needed to keep generated
    Markdown byte-identical across runs.
    """
    conn = connect()
    query = "SELECT * FROM stage_results WHERE target = ?"
    params: list[Any] = [target]
    if stage is not None:
        query += " AND stage = ?"
        params.append(stage)
    if packages is not None:
        if not packages:
            return {}
        placeholders = ",".join("?" for _ in packages)
        query += f" AND package IN ({placeholders})"
        params.extend(packages)
    query += " ORDER BY package"

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for row in conn.execute(query, params).fetchall():
        entry = _stage_entry(row)
        assert entry is not None  # row came from a real fetched row, never None
        result.setdefault(row["stage"], {})[row["package"]] = entry
    return result


def set_stage(
    package: str,
    stage: str,
    target: str,
    run_id: int | None,
    state: str,
    **fields: Any,
) -> None:
    """Insert or wholesale-replace a stage row.

    Mirrors `build_status["stages"][stage][pkg] = entry` in the old code: any
    column not passed in `fields` is reset (including `hashes_json`, which is
    only reinstated by `finalize_stage`). The one caller that must NOT replace
    the row -- the cache-hit path, which only touches `reason` -- uses
    `update_reason` instead.
    """
    conn = connect()
    values = {col: fields.get(col) for col in _STAGE_ENTRY_COLUMNS}
    values["has_devel"] = int(bool(values["has_devel"] or 0))
    values["force_run"] = int(bool(values["force_run"] or 0))
    values["state"] = state
    conn.execute(
        """
        INSERT INTO stage_results
            (package, stage, target, state, version, reason, log, path,
             build_id, errors, warnings, has_devel, force_run,
             started_at, completed_at, run_id, updated_at)
        VALUES
            (:package, :stage, :target, :state, :version, :reason, :log, :path,
             :build_id, :errors, :warnings, :has_devel, :force_run,
             :started_at, :completed_at, :run_id, :updated_at)
        ON CONFLICT(package, stage, target) DO UPDATE SET
            state=excluded.state, version=excluded.version, reason=excluded.reason,
            log=excluded.log, path=excluded.path, build_id=excluded.build_id,
            errors=excluded.errors, warnings=excluded.warnings,
            has_devel=excluded.has_devel, force_run=excluded.force_run,
            started_at=excluded.started_at, completed_at=excluded.completed_at,
            hashes_json=NULL, run_id=excluded.run_id, updated_at=excluded.updated_at
        """,
        {
            "package": package,
            "stage": stage,
            "target": target,
            "run_id": run_id,
            "updated_at": now_epoch(),
            **values,
        },
    )
    conn.commit()


def update_reason(package: str, stage: str, target: str, reason: str) -> None:
    """Update only the `reason` column of an existing row. No-op if the row is absent."""
    conn = connect()
    conn.execute(
        """
        UPDATE stage_results SET reason = ?, updated_at = ?
        WHERE package = ? AND stage = ? AND target = ?
        """,
        (reason, now_epoch(), package, stage, target),
    )
    conn.commit()


def update_state(package: str, stage: str, target: str, state: str) -> None:
    """Update only the `state` column of an existing row. No-op if the row is absent.

    Used by poll_copr_status: an async copr submission is re-polled later and
    only its state changes -- everything else (hashes, log path, build_id)
    must survive untouched, same reasoning as update_reason.
    """
    conn = connect()
    conn.execute(
        """
        UPDATE stage_results SET state = ?, updated_at = ?
        WHERE package = ? AND stage = ? AND target = ?
        """,
        (state, now_epoch(), package, stage, target),
    )
    conn.commit()


def finalize_stage(
    package: str,
    stage: str,
    target: str,
    started_at: int,
    hashes: dict[str, Any],
    reason: str | None = None,
    update_hashes: bool = True,
) -> None:
    """DB form of the old `inject_stage_meta`: stamp started_at, maybe hashes/reason,
    and clear force_run. No-op if the row doesn't exist.
    """
    conn = connect()
    row = conn.execute(
        "SELECT state FROM stage_results WHERE package = ? AND stage = ? AND target = ?",
        (package, stage, target),
    ).fetchone()
    if row is None:
        return

    set_clauses = ["started_at = ?", "force_run = 0", "updated_at = ?"]
    params: list[Any] = [started_at, now_epoch()]
    if update_hashes and row["state"] == "success":
        set_clauses.append("hashes_json = ?")
        params.append(json.dumps(hashes, sort_keys=True))
    if reason is not None:
        set_clauses.append("reason = ?")
        params.append(reason)
    params.extend([package, stage, target])

    conn.execute(
        f"""
        UPDATE stage_results SET {", ".join(set_clauses)}
        WHERE package = ? AND stage = ? AND target = ?
        """,
        params,
    )
    conn.commit()


def clear_stage(stage: str, target: str, packages: list[str]) -> None:
    """Delete stage rows for the given packages only (scoped -- see bugs.md/#8:
    the old init_stage() wiped the WHOLE stage dict regardless of PACKAGE filter).
    """
    conn = connect()
    if not packages:
        return
    placeholders = ",".join("?" for _ in packages)
    conn.execute(
        f"DELETE FROM stage_results WHERE stage = ? AND target = ? AND package IN ({placeholders})",
        [stage, target, *packages],
    )
    conn.commit()


def set_force_run(
    packages: list[str] | set[str],
    stages: tuple[str, ...],
    target: str,
) -> list[str]:
    """Set force_run=1 for existing (package, stage, target) rows. Returns sorted affected packages."""
    conn = connect()
    affected: set[str] = set()
    for stage in stages:
        for pkg in packages:
            cur = conn.execute(
                """
                UPDATE stage_results SET force_run = 1, updated_at = ?
                WHERE package = ? AND stage = ? AND target = ?
                """,
                (now_epoch(), pkg, stage, target),
            )
            if cur.rowcount > 0:
                affected.add(pkg)
    conn.commit()
    return sorted(affected)


def forget_package(package: str) -> None:
    """Delete a package's stage rows and artifacts across all targets."""
    conn = connect()
    conn.execute("DELETE FROM stage_results WHERE package = ?", (package,))
    conn.execute("DELETE FROM artifacts WHERE package = ?", (package,))
    conn.commit()


# --- artifacts --------------------------------------------------------------


def record_artifact(
    path: str,
    realm: str,
    kind: str,
    package: str,
    target: str,
    version: str | None,
) -> None:
    """Record an artifact's path/size/mtime. Upserts on (realm, path).

    Stats the file if it exists; size_bytes/mtime are NULL if it doesn't
    (recorded anyway so `db-usage --usage` can flag it as missing).
    """
    conn = connect()
    p = Path(path)
    try:
        st = p.stat()
        size_bytes: int | None = st.st_size
        mtime: int | None = int(st.st_mtime)
    except OSError:
        size_bytes = None
        mtime = None
    conn.execute(
        """
        INSERT INTO artifacts (path, realm, kind, package, target, version, size_bytes, mtime, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(realm, path) DO UPDATE SET
            kind=excluded.kind, package=excluded.package, target=excluded.target,
            version=excluded.version, size_bytes=excluded.size_bytes,
            mtime=excluded.mtime, recorded_at=excluded.recorded_at
        """,
        (path, realm, kind, package, target, version, size_bytes, mtime, now_epoch()),
    )
    conn.commit()


def artifacts(
    package: str | None = None,
    target: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    """Return artifact rows matching the given filters."""
    conn = connect()
    query = "SELECT * FROM artifacts WHERE 1=1"
    params: list[Any] = []
    if package is not None:
        query += " AND package = ?"
        params.append(package)
    if target is not None:
        query += " AND target = ?"
        params.append(target)
    if kind is not None:
        query += " AND kind = ?"
        params.append(kind)
    query += " ORDER BY path"
    return [_row_dict(row) for row in conn.execute(query, params).fetchall()]


def delete_artifact(realm: str, path: str) -> None:
    """Delete an artifact row (does not unlink the file -- callers do that)."""
    conn = connect()
    conn.execute("DELETE FROM artifacts WHERE realm = ? AND path = ?", (realm, path))
    conn.commit()


# --- reset -------------------------------------------------------------


def reset() -> None:
    """Clear stage_results and runs, but keep artifacts.

    Used by `make clean-logs` -- dropping `artifacts` here would orphan
    every tracked file on disk with no record of what it is or how to find
    it again. stage_results is deleted before runs to satisfy the
    stage_results.run_id foreign key.
    """
    conn = connect()
    conn.execute("DELETE FROM stage_results")
    conn.execute("DELETE FROM runs")
    conn.commit()
