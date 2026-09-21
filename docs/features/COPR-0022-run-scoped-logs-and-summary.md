# COPR-0022. Run-scoped logs and a durable nightly summary

**Tags:** #daily #diagnostics #logs

## User Story

As a maintainer, I want each night's build logs kept under a run identifier and a
summary of what happened committed somewhere durable, so that a failure from two
nights ago isn't simply gone by the time I look for it.

## Behavior

Build logs nest under both a run identifier and the build target:

```text
logs/runs/<run_id>/<target>/<package>/
  00-spec.log
  05-vendor.log
  10-srpm.log
  20-mock.log
  21-mock-build.log
  21-mock-root.log
  30-copr.log
  30-copr-chroots.log
  31-copr-<chroot>.log
logs/runs/latest -> <run_id>/     # symlink, refreshed each run, for humans only
```

`<run_id>` is `runs.id`, the same primary key `stage_results`/`stage_history`
already thread through every `set_stage()`/`finalize_stage()` call — no second
identity was invented. `<target>` is the `build_db` target key (e.g.
`fedora-44-x86_64`), not merely `<distro>-<version>`: a bare distro/version segment
would still collide between two arches of the same Fedora version, which is exactly
the collision this feature exists to fix (`COPR-0021`'s per-chroot Copr rows and
`COPR-0020`'s aarch64 builds both add a second `target` per `distro`-`version`).
`get_run_log_dir(run_id, target)` / `get_package_log_dir(pkg, run_id, target)`
(`lib/paths.py`) compute these paths; every stage script's `run_for_package()`
already has both values in scope next to its `build_db.set_stage(...)` call, so
threading them through was a parameter add, not new plumbing.

A run's log dir is no longer destroyed at the start of the next run — `full-cycle.py`
used to `rmtree` `logs/build/<pkg>/` in `main()` before starting; that step is gone.
Instead, `lib/log_retention.py` keeps the newest `LOG_RETENTION_RUNS` run
directories (default 10; `.env`/env var, `make prune-logs KEEP=<n> CONFIRM=1` to run
by hand, dry-run without `CONFIRM=1`) and prunes the rest after each run starts.
Nothing outside `logs/runs/` (`logs/make`, `logs/.pipeline.lock`,
`logs/build-report.db.last`) is ever a prune candidate — they're siblings of
`logs/runs/`, not inside it.

`pkg-log-analysis.py` resolves a package's log dir(s) itself now (`resolve_log_dirs()`):
without `--run-id`/`--target`, it picks the newest run under `logs/runs/` that has a
directory for the package, and analyzes *every* target within that run (a matrix
night logs the same package once per chroot, in the same `run_id`, and all of them
matter). `--output <file>` additionally renders a Markdown summary listing what was
clean, what had issues (with the collected issue lines and the exact log dir), and
what had no logs at all. `make stage-log-analyze LOG_SUMMARY_OUTPUT=docs/nightly-summary.md`
is how `_update-daily` invokes this; a plain `make stage-log-analyze` (no
`LOG_SUMMARY_OUTPUT`) skips `--output` entirely so an ad-hoc run never rewrites the
committed file.

`docs/nightly-summary.md` is the "durable" half: `logs/` itself is gitignored, so the
summary is committed and overwritten each night — git history is the archive
(`git log -p docs/nightly-summary.md` gives every past night), which needs no
retention policy of its own. `_update-daily` stages it (`git add`) only if
`stage-log-analyze` actually wrote it, so an empty package set can't fail the commit
step on a missing file.

`delete-package.py` used the old flat layout's `<pkg-log-dir>.parent.iterdir()` trick
for case-insensitive name discovery; it now globs `logs/runs/*/*/<pkg>` via
`lib.paths.iter_package_log_dirs()` and removes every match across every run/target
still on disk.

## Implementation

- `lib/paths.py`: `RUNS_LOG_DIR`, `get_run_log_dir()`, `get_package_log_dir()`,
  `iter_package_log_dirs()`.
- `lib/log_retention.py` (new): `list_run_dirs_newest_first()`, `prune_run_logs()`,
  `refresh_latest_link()`, `retention_from_env()`.
- `scripts/prune-logs.py` (new) + `make prune-logs`.
- `scripts/pkg-log-analysis.py`: `resolve_log_dirs()`, `collect_issues()` (the old
  print-per-section body, now building a line list reused by both the stdout printer
  and the Markdown renderer), `render_markdown_summary()`, `--run-id`/`--target`/
  `--output` flags.
- Every stage script (`stage-spec.py`, `stage-vendor.py`, `stage-srpm.py`,
  `stage-mock.py`, `stage-copr.py`) and `lib/copr.py`'s `fetch_failed_chroot_logs()`
  now pass `run_id`/`target` into `get_package_log_dir()`.
  `fetch_failed_chroot_logs()` falls back to `build_db.latest_run(target)` when
  called without a `run_id` (gen-report.py's standalone poll has none of its own).
- `full-cycle.py`: the old rmtree loop is gone; `main()` now creates this run's log
  dir, refreshes `logs/runs/latest`, and prunes right after `setup_run()`.
- `Makefile`: `clean-logs` removes `logs/runs` (was `logs/build`); `stage-log-analyze`
  gained `LOG_SUMMARY_OUTPUT`; `_update-daily` passes it and stages
  `docs/nightly-summary.md`; new `prune-logs` target.
- Live-tailing mock's resultdir via a bind-mount (`stage-mock.py`'s
  `copy_mock_results()`) stays a separate, cheaper follow-up — independent of this
  path-layout change, per the original plan.

## Quirks & Decisions

- `<target>` (not `<distro>-<version>`) is the chroot segment — see Behavior above.
  This edits the original plan, which used `<distro>-<version>` and would have
  reintroduced the arch collision once aarch64 (`COPR-0020`) lands.
- Retention is **count-based** (newest N runs), not age-based: predictable regardless
  of how often the pipeline actually runs, and needs no clock reasoning in tests.
- `logs/runs/latest` is a convenience symlink for a human on the host; nothing in the
  pipeline reads it back.
- The pre-existing `logs/build/` tree is not migrated; it is simply orphaned (removed
  by a future `make clean-logs`). No `stage_results.log` value in `build-report.db`
  needs it: `host_path()` resolves any repo-relative string, and `db-artifacts.py`
  never prunes log artifacts regardless of layout.

## Testing

- Unit (`tests/test_paths_complete.py`): `get_package_log_dir()`/`get_run_log_dir()`
  resolve without collision across two chroots of the same package in the same run,
  and across two runs of the same (package, target); `iter_package_log_dirs()` finds
  a package across every run/target on disk.
- Unit (`tests/test_log_retention.py`, `tests/test_prune_logs.py`): retention keeps
  exactly the newest N run dirs, never touches non-`logs/runs/` siblings, and the
  `prune-logs` CLI's dry-run vs. `--confirm` behavior.
- Unit (`tests/test_pkg_log_analysis.py`): `resolve_log_dirs()` picks the newest run
  with the package, returns every target within a matrix run, and an explicit
  `--run-id`/`--target` pins one directory even if it doesn't exist; `--output` writes
  a Markdown summary linking to the real log dir.
- Integration (`tests/integration/test_make_targets.py`): no rmtree of a prior run's
  logs; `stage-log-analyze` still runs between `readme` and the commit and writes
  `docs/nightly-summary.md`, which is staged.

## Status

Implemented
