# COPR-0015. Persist build state in build-report.db

**Tags:** #persistence #state #caching

## User Story

As a maintainer, I want every stage's outcome, per package and per Fedora version,
recorded durably, so that reruns skip unchanged work and disk usage/artifacts can be
audited without re-deriving state from logs.

## Behavior

`build-report.db` (sqlite, gitignored) is the single source of truth for build state:
`runs` (one row per invocation), `stage_results` (per-stage *current* state, keyed by
`(package, stage, target)`), `stage_history` (append-only, keyed by
`(package, stage, target, run_id)` — one row per attempt, never overwritten),
`artifacts` (paths/sizes/`sha256`/`arch` of every SRPM, vendor tarball, mock-built
RPM, and log). `make db-usage [VERIFY=1]`/`make db-prune [CONFIRM=1]` report and
reclaim disk usage by package × target; `make db-shell` opens an interactive
sqlite3 shell; `make db-export [FORMAT=yaml|json] [OUTPUT=path]` snapshots every
table to a deterministic, sorted yaml/json file for offline diffing.

`db-usage`/`db-prune`/`db-shell` all read `artifacts.path`, recorded as an
absolute *container* path (`/work/...` under the repo/vendor-store realms, or a
podman-named-volume path with no host equivalent at all under `rpmbuild-volume`).
`lib.paths.host_path(realm, path)` resolves the repo/vendor-store realms to a real
path on the host running outside the container; `db-usage`/`db-prune` use it to
work from the host too (`rpmbuild-volume` rows are reported, but their size/path
can't be resolved that way and say so).

`artifacts.sha256` detects on-disk corruption within a target (the wrong-chroot case
is already caught by the per-chroot `local-repo/<target>/` layout): it is computed
once per file and recomputed only when the file's recorded `size_bytes`/`mtime`
changes, so a normal run doesn't re-hash every RPM. `artifacts.arch` records the
artifact's own architecture — distinct from its target's arch for a `noarch`
subpackage.

`stage_results` also keeps the last **successful** attempt's `version`/`log`/
`build_id`/timestamp alongside the last attempt's (`last_success_*` columns) — a
failed rebuild overwrites `version`/`log`/`build_id` but never `last_success_*`,
so the previous known-good build stays discoverable. `stage_history` is what answers
"why did package X rebuild in run N": every `set_stage()`/`finalize_stage()`/
`update_reason()`/`update_state()` call appends a row for the current `run_id`
instead of overwriting in place, since `run_id` already threads through every call
site.

`db-export`'s deterministic snapshot is the natural input for the docs-drift CI
check in [COPR-0012](COPR-0012-docs-generation.md)'s BUG-0031.

## Implementation

- `lib/build_db.py`, `lib/cache.py`, `lib/pipeline.py`.
- Composite key `(package, stage, target)` on `stage_results`, row upserts instead of
  full-file rewrites (migrated from a `build-report.yaml` full-rewrite scheme).
- `stage_history` rows are written best-effort alongside `stage_results` in the same
  transaction; calls with no `run_id` (tests, ad-hoc scripts) write no history row.
- Schema migrations are ordered and additive (`_MIGRATIONS`, applied from
  `PRAGMA user_version` upward) so existing databases gain new tables/columns without
  losing data.

## Testing

### Unit

- `tests/test_build_db.py`, `tests/test_db_artifacts.py`,
  `tests/test_artifact_recording.py`, `tests/test_cache_and_yaml_utils.py`.

## Status

Implemented
