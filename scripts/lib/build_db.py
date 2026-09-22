"""SQLite storage for build-report data: run history, per-stage results,
append-only attempt history, artifacts. #COPR-0015.

Replaces build-report.yaml. Schema key is `target` (the mock chroot triple, e.g.
`fedora-44-x86_64`), not `fedora_version` -- see docs/TODO.md "Build matrix" for why.

See docs/ROADMAP.md Epic 3 for remaining follow-ups (artifact sha256/arch, etc).
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import paths

STAGES = ["validate", "spec", "vendor", "srpm", "mock", "copr"]

SCHEMA_VERSION = 3

_SCHEMA_V1 = """
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

# #COPR-0015, #BUG-0063, #BUG-0059: append-only attempt history, plus
# last-known-good columns on stage_results that a later failure must not clobber.
_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS stage_history (
  package        TEXT    NOT NULL,
  stage          TEXT    NOT NULL,
  target         TEXT    NOT NULL,
  run_id         INTEGER NOT NULL REFERENCES runs(id),
  state          TEXT    NOT NULL,
  reason         TEXT,
  version        TEXT,
  log            TEXT,
  build_id       INTEGER,
  started_at     INTEGER,
  completed_at   INTEGER,
  recorded_at    INTEGER NOT NULL,
  PRIMARY KEY (package, stage, target, run_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS stage_history_pkg ON stage_history(package, stage, target);
CREATE INDEX IF NOT EXISTS stage_history_run ON stage_history(run_id);

ALTER TABLE stage_results ADD COLUMN last_success_version  TEXT;
ALTER TABLE stage_results ADD COLUMN last_success_log       TEXT;
ALTER TABLE stage_results ADD COLUMN last_success_build_id  INTEGER;
ALTER TABLE stage_results ADD COLUMN last_success_at        INTEGER;
"""

# #COPR-0015, #BUG-0061, #BUG-0065: sha256 (corruption detection, mtime/size-guarded
# so a normal run doesn't re-hash every RPM) and arch (a noarch subpackage's arch can
# differ from its target's) on artifacts. Both nullable -- existing rows migrate as
# NULL and fill in lazily on the next record_artifact() call for that path.
_SCHEMA_V3 = """
ALTER TABLE artifacts ADD COLUMN sha256 TEXT;
ALTER TABLE artifacts ADD COLUMN arch   TEXT;
"""

# Ordered, additive migrations: index i takes a db from user_version i to i+1.
# Each step commits and stamps its own version before the next runs, so a
# migration that dies partway through resumes cleanly on the next connect().
_MIGRATIONS: list[str] = [_SCHEMA_V1, _SCHEMA_V2, _SCHEMA_V3]

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
    """Apply each pending migration step in order, stamping user_version as it goes.

    `_MIGRATIONS[i]` takes the db from user_version `i` to `i+1` -- all steps are
    additive (CREATE TABLE IF NOT EXISTS / ALTER TABLE ADD COLUMN), so a fresh db
    and an old db converge on the same schema.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    while version < SCHEMA_VERSION:
        conn.executescript(_MIGRATIONS[version])
        version += 1
        conn.execute(f"PRAGMA user_version = {version}")
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
    # last_success_* has its own accessor (last_success()) rather than living here.
    entry.pop("run_id", None)
    entry.pop("updated_at", None)
    entry.pop("package", None)
    entry.pop("stage", None)
    entry.pop("target", None)
    entry.pop("last_success_version", None)
    entry.pop("last_success_log", None)
    entry.pop("last_success_build_id", None)
    entry.pop("last_success_at", None)
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


def _record_history(
    conn: sqlite3.Connection,
    package: str,
    stage: str,
    target: str,
    run_id: int | None,
    *,
    state: str,
    reason: str | None,
    version: str | None,
    log: str | None,
    build_id: int | None,
    started_at: int | None,
    completed_at: int | None,
) -> None:
    """Append/update this run's `stage_history` row. No-op if `run_id` is None.

    #COPR-0015, #BUG-0063. Keyed by (package, stage, target, run_id): a real
    upsert only when the same run touches a stage more than once (set_stage
    then finalize_stage) -- a different run_id always lands a fresh row, so
    history is never overwritten across runs.
    """
    if run_id is None:
        return
    conn.execute(
        """
        INSERT INTO stage_history
            (package, stage, target, run_id, state, reason, version, log,
             build_id, started_at, completed_at, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(package, stage, target, run_id) DO UPDATE SET
            state=excluded.state, reason=excluded.reason, version=excluded.version,
            log=excluded.log, build_id=excluded.build_id,
            started_at=excluded.started_at, completed_at=excluded.completed_at,
            recorded_at=excluded.recorded_at
        """,
        (
            package,
            stage,
            target,
            run_id,
            state,
            reason,
            version,
            log,
            build_id,
            started_at,
            completed_at,
            now_epoch(),
        ),
    )


def stage_history(
    package: str | None = None,
    stage: str | None = None,
    target: str | None = None,
    run_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return stage_history rows matching the given filters, oldest first.

    #COPR-0015, #BUG-0063. `limit`, if given, returns the *most recent* `limit`
    rows (still returned oldest-first) rather than an arbitrary prefix.
    """
    conn = connect()
    query = "SELECT * FROM stage_history WHERE 1=1"
    params: list[Any] = []
    if package is not None:
        query += " AND package = ?"
        params.append(package)
    if stage is not None:
        query += " AND stage = ?"
        params.append(stage)
    if target is not None:
        query += " AND target = ?"
        params.append(target)
    if run_id is not None:
        query += " AND run_id = ?"
        params.append(run_id)
    query += " ORDER BY run_id DESC" if limit is not None else " ORDER BY run_id ASC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = [_row_dict(row) for row in conn.execute(query, params).fetchall()]
    return list(reversed(rows)) if limit is not None else rows


def last_success(package: str, stage: str, target: str) -> dict[str, Any] | None:
    """Return the last successful attempt's {version, log, build_id, at}, or None.

    #COPR-0015, #BUG-0059. Survives subsequent failed reruns of the same
    (package, stage, target) -- unlike `version`/`log`/`build_id` on the main
    row, which a failure overwrites.
    """
    conn = connect()
    row = conn.execute(
        """
        SELECT last_success_version AS version, last_success_log AS log,
               last_success_build_id AS build_id, last_success_at AS at
        FROM stage_results WHERE package = ? AND stage = ? AND target = ?
        """,
        (package, stage, target),
    ).fetchone()
    if row is None or row["at"] is None:
        return None
    return _row_dict(row)


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
    only reinstated by `finalize_stage`) -- except `last_success_*`
    (#BUG-0059), which is deliberately carried forward on anything but a
    success, and `stage_history` (#BUG-0063), which is append-only and never
    reset by design. The one caller that must NOT replace the row -- the
    cache-hit path, which only touches `reason` -- uses `update_reason`
    instead.
    """
    conn = connect()
    values = {col: fields.get(col) for col in _STAGE_ENTRY_COLUMNS}
    values["has_devel"] = int(bool(values["has_devel"] or 0))
    values["force_run"] = int(bool(values["force_run"] or 0))
    values["state"] = state
    is_success = state == "success"
    conn.execute(
        """
        INSERT INTO stage_results
            (package, stage, target, state, version, reason, log, path,
             build_id, errors, warnings, has_devel, force_run,
             started_at, completed_at, run_id, updated_at,
             last_success_version, last_success_log, last_success_build_id,
             last_success_at)
        VALUES
            (:package, :stage, :target, :state, :version, :reason, :log, :path,
             :build_id, :errors, :warnings, :has_devel, :force_run,
             :started_at, :completed_at, :run_id, :updated_at,
             :last_success_version, :last_success_log, :last_success_build_id,
             :last_success_at)
        ON CONFLICT(package, stage, target) DO UPDATE SET
            state=excluded.state, version=excluded.version, reason=excluded.reason,
            log=excluded.log, path=excluded.path, build_id=excluded.build_id,
            errors=excluded.errors, warnings=excluded.warnings,
            has_devel=excluded.has_devel, force_run=excluded.force_run,
            started_at=excluded.started_at, completed_at=excluded.completed_at,
            hashes_json=NULL, run_id=excluded.run_id, updated_at=excluded.updated_at,
            last_success_version=CASE WHEN excluded.state='success'
                THEN excluded.last_success_version ELSE stage_results.last_success_version END,
            last_success_log=CASE WHEN excluded.state='success'
                THEN excluded.last_success_log ELSE stage_results.last_success_log END,
            last_success_build_id=CASE WHEN excluded.state='success'
                THEN excluded.last_success_build_id ELSE stage_results.last_success_build_id END,
            last_success_at=CASE WHEN excluded.state='success'
                THEN excluded.last_success_at ELSE stage_results.last_success_at END
        """,
        {
            "package": package,
            "stage": stage,
            "target": target,
            "run_id": run_id,
            "updated_at": now_epoch(),
            "last_success_version": values["version"] if is_success else None,
            "last_success_log": values["log"] if is_success else None,
            "last_success_build_id": values["build_id"] if is_success else None,
            "last_success_at": now_epoch() if is_success else None,
            **values,
        },
    )
    _record_history(
        conn,
        package,
        stage,
        target,
        run_id,
        state=state,
        reason=values["reason"],
        version=values["version"],
        log=values["log"],
        build_id=values["build_id"],
        started_at=values["started_at"],
        completed_at=values["completed_at"],
    )
    conn.commit()


def update_reason(
    package: str, stage: str, target: str, reason: str, run_id: int | None = None
) -> None:
    """Update only the `reason` column of an existing row. No-op if the row is absent.

    `run_id`, if given, mirrors the change into that run's `stage_history` row
    (#BUG-0063) -- the cache-hit path calls this with the *current* run's id
    even though the row's own `run_id` column still points at whichever run
    last actually executed the stage, so history isn't misattributed to that
    older run.
    """
    conn = connect()
    conn.execute(
        """
        UPDATE stage_results SET reason = ?, updated_at = ?
        WHERE package = ? AND stage = ? AND target = ?
        """,
        (reason, now_epoch(), package, stage, target),
    )
    if run_id is not None:
        row = conn.execute(
            "SELECT * FROM stage_results WHERE package = ? AND stage = ? AND target = ?",
            (package, stage, target),
        ).fetchone()
        if row is not None:
            _record_history(
                conn,
                package,
                stage,
                target,
                run_id,
                state=row["state"],
                reason=reason,
                version=row["version"],
                log=row["log"],
                build_id=row["build_id"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )
    conn.commit()


def update_state(
    package: str, stage: str, target: str, state: str, run_id: int | None = None
) -> None:
    """Update only the `state` column of an existing row. No-op if the row is absent.

    Used by poll_copr_status: an async copr submission is re-polled later and
    only its state changes -- everything else (hashes, log path, build_id)
    must survive untouched, same reasoning as update_reason. `run_id` mirrors
    the change into `stage_history` the same way update_reason's does.
    """
    conn = connect()
    conn.execute(
        """
        UPDATE stage_results SET state = ?, updated_at = ?
        WHERE package = ? AND stage = ? AND target = ?
        """,
        (state, now_epoch(), package, stage, target),
    )
    if run_id is not None:
        row = conn.execute(
            "SELECT * FROM stage_results WHERE package = ? AND stage = ? AND target = ?",
            (package, stage, target),
        ).fetchone()
        if row is not None:
            _record_history(
                conn,
                package,
                stage,
                target,
                run_id,
                state=state,
                reason=row["reason"],
                version=row["version"],
                log=row["log"],
                build_id=row["build_id"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
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

    Mirrors the refined `started_at`/`reason` into this run's `stage_history` row
    (#BUG-0063) -- called right after `set_stage()` in the same run, so it updates
    the row `set_stage()` just created rather than starting a new one.
    """
    conn = connect()
    row = conn.execute(
        "SELECT * FROM stage_results WHERE package = ? AND stage = ? AND target = ?",
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
    _record_history(
        conn,
        package,
        stage,
        target,
        row["run_id"],
        state=row["state"],
        reason=reason if reason is not None else row["reason"],
        version=row["version"],
        log=row["log"],
        build_id=row["build_id"],
        started_at=started_at,
        completed_at=row["completed_at"],
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
    """Delete a package's stage rows, history, and artifacts across all targets."""
    conn = connect()
    conn.execute("DELETE FROM stage_history WHERE package = ?", (package,))
    conn.execute("DELETE FROM stage_results WHERE package = ?", (package,))
    conn.execute("DELETE FROM artifacts WHERE package = ?", (package,))
    conn.commit()


def known_packages() -> set[str]:
    """Return every distinct package name recorded in stage_results or artifacts."""
    conn = connect()
    names = {r[0] for r in conn.execute("SELECT DISTINCT package FROM stage_results")}
    names |= {r[0] for r in conn.execute("SELECT DISTINCT package FROM artifacts")}
    return names


# --- artifacts --------------------------------------------------------------


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def record_artifact(
    path: str,
    realm: str,
    kind: str,
    package: str,
    target: str,
    version: str | None,
    arch: str | None = None,
) -> None:
    """Record an artifact's path/size/mtime/sha256/arch. Upserts on (realm, path).

    Stats the file if it exists; size_bytes/mtime are NULL if it doesn't
    (recorded anyway so `db-usage --usage` can flag it as missing).

    #COPR-0015, #BUG-0061: sha256 is only (re)computed when the file's
    `size_bytes`/`mtime` differ from the existing row -- hashing every RPM on
    every run has a real I/O cost, so an unchanged file just carries its prior
    sha256 forward. A file that no longer stats (size_bytes/mtime both None)
    keeps whatever sha256 was last recorded rather than clearing it.
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

    prior = conn.execute(
        "SELECT size_bytes, mtime, sha256 FROM artifacts WHERE realm = ? AND path = ?",
        (realm, path),
    ).fetchone()
    if (
        prior is not None
        and prior["sha256"] is not None
        and prior["size_bytes"] == size_bytes
        and prior["mtime"] == mtime
    ):
        sha256 = prior["sha256"]
    elif size_bytes is not None:
        sha256 = _sha256_file(p)
    else:
        sha256 = prior["sha256"] if prior is not None else None

    conn.execute(
        """
        INSERT INTO artifacts
            (path, realm, kind, package, target, version, size_bytes, mtime,
             sha256, arch, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(realm, path) DO UPDATE SET
            kind=excluded.kind, package=excluded.package, target=excluded.target,
            version=excluded.version, size_bytes=excluded.size_bytes,
            mtime=excluded.mtime, sha256=excluded.sha256, arch=excluded.arch,
            recorded_at=excluded.recorded_at
        """,
        (
            path,
            realm,
            kind,
            package,
            target,
            version,
            size_bytes,
            mtime,
            sha256,
            arch,
            now_epoch(),
        ),
    )
    conn.commit()


def verify_artifact(
    realm: str, path: str, resolved_path: Path | None = None
) -> bool | None:
    """Re-hash an artifact and compare against its recorded sha256.

    #COPR-0015, #BUG-0061. Returns True/False, or None if the row or file is
    missing, or no sha256 was ever recorded for it (a stage that predates this
    column, or a file that has never been re-touched since). Deliberately not
    called from `artifacts_present()`/`is_cached()` -- those run per package
    per pipeline invocation and would re-hash the entire local repo on every
    build; this is for on-demand use (`db-artifacts.py --usage --verify`).

    `resolved_path`, if given, is hashed instead of the recorded `path` --
    #BUG-0062: `path` is a container-absolute path, so a caller running
    outside the container (having resolved it via `lib.paths.host_path()`)
    passes the real location here.
    """
    conn = connect()
    row = conn.execute(
        "SELECT sha256 FROM artifacts WHERE realm = ? AND path = ?",
        (realm, path),
    ).fetchone()
    if row is None or row["sha256"] is None:
        return None
    actual = _sha256_file(resolved_path or Path(path))
    if actual is None:
        return None
    return actual == row["sha256"]


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


def delete_artifacts_for_target(target: str, realm: str, kind: str) -> None:
    """Delete every artifact row for one (target, realm, kind).

    Used by `db-artifacts.py --forget-repo` (the fixed `make clean-localrepo`,
    docs/CHANGELOG.md 2026-08-11) to drop ledger rows for a target's
    local-repo RPMs after `rm -rf local-repo/<target>/` -- does not unlink
    files, callers do that first.
    """
    conn = connect()
    conn.execute(
        "DELETE FROM artifacts WHERE target = ? AND realm = ? AND kind = ?",
        (target, realm, kind),
    )
    conn.commit()


# --- export (#COPR-0015, #BUG-0060) ----------------------------------------


def all_runs() -> list[dict[str, Any]]:
    """Return every `runs` row, ordered by id. Used by `db-export`."""
    conn = connect()
    return [_row_dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id")]


def all_stage_results() -> list[dict[str, Any]]:
    """Return every `stage_results` row (unlike `stage_map()`, flat and
    ungrouped, `package`/`stage`/`target` included) with `hashes_json`
    decoded to `hashes`. Used by `db-export`.
    """
    conn = connect()
    rows = []
    for row in conn.execute(
        "SELECT * FROM stage_results ORDER BY package, stage, target"
    ):
        entry = _row_dict(row)
        hashes_json = entry.pop("hashes_json", None)
        if hashes_json is not None:
            entry["hashes"] = json.loads(hashes_json)
        rows.append(entry)
    return rows


def all_stage_history() -> list[dict[str, Any]]:
    """Return every `stage_history` row, ordered by run_id. Used by `db-export`."""
    conn = connect()
    return [
        _row_dict(row)
        for row in conn.execute(
            "SELECT * FROM stage_history ORDER BY run_id, package, stage, target"
        )
    ]


def all_artifacts() -> list[dict[str, Any]]:
    """Return every `artifacts` row, ordered by realm/path. Used by `db-export`."""
    conn = connect()
    return [
        _row_dict(row)
        for row in conn.execute("SELECT * FROM artifacts ORDER BY realm, path")
    ]


def export_snapshot() -> dict[str, list[dict[str, Any]]]:
    """Return the whole db as {table: [row, ...]}, each list sorted
    deterministically -- for offline diffing (`make db-export`).
    """
    return {
        "runs": all_runs(),
        "stage_results": all_stage_results(),
        "stage_history": all_stage_history(),
        "artifacts": all_artifacts(),
    }


def latest_runs_by_target() -> list[dict[str, Any]]:
    """Return the most recent `runs` row per distinct `target`, ordered by
    target. #BUG-0031: `gen-report.py` only ever reads `latest_run(target)`
    for whichever one target it's rendering -- exporting every historical run
    (`all_runs()`) into a committed snapshot would grow it unboundedly for no
    reason a docs render needs.
    """
    conn = connect()
    return [
        _row_dict(row)
        for row in conn.execute(
            "SELECT * FROM runs WHERE id IN "
            "(SELECT MAX(id) FROM runs GROUP BY target) ORDER BY target"
        )
    ]


# Columns stage_map()/_stage_entry() strip from a stage_results row before
# handing it to a caller -- kept alongside stage_map_from_export() so the two
# reshape identically. See _stage_entry() above for the live-query version.
_STAGE_ENTRY_DROP_FIELDS = (
    "run_id",
    "updated_at",
    "package",
    "stage",
    "target",
    "last_success_version",
    "last_success_log",
    "last_success_build_id",
    "last_success_at",
)


def stage_map_from_export(
    rows: list[dict[str, Any]], target: str
) -> dict[str, dict[str, dict[str, Any]]]:
    """Reshape all_stage_results()-style flat rows (read back from a
    db-export/db-export-docs snapshot) into stage_map()'s {stage: {package:
    entry}} shape, filtered to `target`.

    #BUG-0031: lets `gen-report.py --db-snapshot` see the identical entry
    shape whether it read live from build-report.db or from a committed
    snapshot, so `collect_packages()` doesn't need two code paths. Relies on
    `rows` already being ordered by package (all_stage_results()'s `ORDER BY
    package, stage, target`) for the per-stage sub-dicts to come out in the
    same deterministic package-name order stage_map() guarantees.
    """
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row.get("target") != target:
            continue
        entry = {k: v for k, v in row.items() if k not in _STAGE_ENTRY_DROP_FIELDS}
        result.setdefault(row["stage"], {})[row["package"]] = entry
    return result


def export_docs_snapshot() -> dict[str, list[dict[str, Any]]]:
    """Return just what `gen-report.py` reads out of the db: the latest run
    per target, and every stage_results row (already "latest" per
    package/stage/target -- it's updated in place, not appended).

    #BUG-0031: this is the narrow, boundedly-sized half of export_snapshot()
    meant to be *committed* (`make db-export-docs` -> docs/db-snapshot.yaml),
    so `gen-report.py --db-snapshot` can re-render the docs body in CI without
    build-report.db (gitignored) or a Copr poll. Deliberately excludes
    stage_history/artifacts -- both append-only and unbounded, and
    gen-report.py reads neither.
    """
    return {
        "runs": latest_runs_by_target(),
        "stage_results": all_stage_results(),
    }


# --- reset -------------------------------------------------------------


def reset() -> None:
    """Clear stage_results, stage_history, and runs, but keep artifacts.

    Used by `make clean-logs` -- dropping `artifacts` here would orphan
    every tracked file on disk with no record of what it is or how to find
    it again. stage_history and stage_results are deleted before runs to
    satisfy their run_id foreign keys.
    """
    conn = connect()
    conn.execute("DELETE FROM stage_history")
    conn.execute("DELETE FROM stage_results")
    conn.execute("DELETE FROM runs")
    conn.commit()
