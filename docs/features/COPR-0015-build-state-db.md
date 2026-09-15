# COPR-0015. Persist build state in build-report.db

**Tags:** #persistence #state #caching

## User Story

As a maintainer, I want every stage's outcome, per package and per Fedora version,
recorded durably, so that reruns skip unchanged work and disk usage/artifacts can be
audited without re-deriving state from logs.

## Behavior

`build-report.db` (sqlite, gitignored) is the single source of truth for build state:
three tables — `runs` (one row per invocation), `stage_results` (per-stage state,
keyed by `(package, stage, target)`), `artifacts` (paths/sizes of every SRPM, vendor
tarball, mock-built RPM, and log). `make db-usage`/`make db-prune [CONFIRM=1]` report
and reclaim disk usage by package × target; `make db-shell` opens an interactive
sqlite3 shell.

## Implementation

- `lib/build_db.py`, `lib/cache.py`, `lib/pipeline.py`.
- Composite key `(package, stage, target)`, row upserts instead of full-file rewrites
  (migrated from a `build-report.yaml` full-rewrite scheme).

## Quirks & Decisions

- Quirk: only "last attempt" is stored per `(package, stage, target)`, not "last
  success" — a failed rebuild overwrites the previous known-good version/log/build_id.
  Proposed: keep `last_success` alongside `last_attempt`. (BUG-0059)
- Quirk: `stage_results.reason` only ever holds the *current* run's explanation — the
  primary key means the next run's `set_stage()` overwrites it in place, so
  reconstructing why an earlier run rebuilt a package requires filesystem evidence
  once the reason is gone.
  Proposed: an append-only `stage_history` table keyed by
  `(package, stage, target, run_id)` — `run_id` already threads through every call
  site, so it's an extra insert with no caller-side plumbing needed. (BUG-0063)
- Quirk: no `sha256` column on `artifacts` to detect on-disk corruption within a
  target (the wrong-chroot case is already caught by the per-chroot `local-repo/
  <target>/` layout).
  Proposed: add it with an mtime/size guard, since hashing every RPM on every run has
  a real I/O cost — fold into the same migration as the `arch` column below. (BUG-0061)
- Quirk: `artifacts` has no `arch` column; a noarch subpackage's arch can differ from
  its target's arch.
  Proposed: same migration as the sha256 addition above. (BUG-0065)
- Quirk: `db-shell`/`db-usage`/`db-prune` only resolve correctly inside the
  container — recorded paths are container-absolute. Can only ever be partially
  fixed: the `rpmbuild-volume` realm has no host path at all.
  Proposed: a host-side fallback for the repo + vendor-store realms only. (BUG-0062)
- Quirk: no `make db-export` (sqlite → yaml/json snapshot) for offline diffing.
  Proposed: add one — also the natural input for the docs-drift CI check in
  [COPR-0012](COPR-0012-docs-generation.md)'s BUG-0031. (BUG-0060)

## Testing

### Unit

- `tests/test_build_db.py`, `tests/test_db_artifacts.py`,
  `tests/test_artifact_recording.py`, `tests/test_cache_and_yaml_utils.py`.

## Status

Implemented
