# COPR-0028. Last-night build stats and error details

**Tags:** #diagnostics #state #tooling

## User Story

As a maintainer, I want one command that tells me how last night's build went — which
targets ran, how long they took, which packages failed and why — so that I don't have
to cross-read `build-report.db`, `logs/runs/` and `stage-log-analyze` output to
answer "did the nightly work?".

## Behavior

`make last-build` prints a read-only report of "last night" from `build-report.db` and
the run-scoped logs ([COPR-0022](COPR-0022-run-scoped-logs-and-summary.md)). It never
writes to the DB or the logs, and runs on the host (`NO_CONTAINER=1`-safe).

**Last night** is the set of `runs` that started within `HOURS` hours (default `12`)
before the start of the newest run. Matrix nights record one run per target, and a
target can have several runs in the window (a failed run retried the same night), so
the report resolves each `(package, stage, target)` to its newest `stage_history` row in
the window: a failure that a later run fixed is not reported.

Sections, in order:

1. **Runs** — one line per run in the window: run id, target, `exit_state`
   (`ok`/`failed`/`running`), start time, duration, package filter.
2. **Stage counts** — per target, packages by state (`success`, `skipped`, `failed`,
   `unknown`) for each stage.
3. **Slowest stages** — the 10 longest `(package, stage, target)` by
   `completed_at - started_at`.
4. **Autohealed** (only when present) — one line per `(package, stage, target)` whose
   `reason` starts with `autoheal:` ([COPR-0029](COPR-0029-build-deps-autoheal.md)),
   success or give-up, with the reason.
5. **Failures** — one entry per `failed` `(package, stage, target)`: version, `reason`,
   `build_id`, and an error excerpt of **at most 20 lines** taken from that stage's logs,
   followed by the path of the log file (with `:<line>` of the first issue when one was
   found) so it can be opened directly. Excerpts come from the same analyzers as
   `stage-log-analyze` (`lib/log_analysis.py`) but never call `dnf`; when an analyzer
   finds nothing, the excerpt falls back to the last lines of the log that match
   `error|fail`, then to the log's last lines. A log that is gone (pruned by
   [retention](COPR-0022-run-scoped-logs-and-summary.md)) prints `log pruned: <path>`
   instead of failing the report.

Options: `PACKAGE=<name>` limits sections 2–4 to one package, `TARGET=<target>` to one
target, `HOURS=<n>` widens or narrows the window, `FORMAT=text|md` (default `text`;
`md` renders log paths as Markdown links). An empty DB or an empty window prints
`no runs found` and exits 0.

Exit code is always 0 for a report that rendered, even when failures are listed: the
command reports, it does not gate.

## Implementation

- `scripts/last-build.py`: `night_runs()`, `latest_rows()`, `stage_counts()`,
  `slowest()`, `failure_excerpt()`, `render()`, CLI (`--package`, `--target`,
  `--hours`, `--format`).
- `Makefile`: `last-build` target passing `PACKAGE`, `TARGET`, `HOURS`, `FORMAT`.
- Reads `runs`/`stage_history` through `lib.build_db.connect()`; log paths come from
  `lib.paths.get_package_log_dir()`.

## Quirks & Decisions

- The window is relative to the newest run, not to `logs/.update-daily-started`
  ([COPR-0026](COPR-0026-gotify-notifications.md)): the marker goes stale after manual
  runs, and the report must also work for a night that never reached `update-daily`.
- `stage_history` (not `stage_results`) is the source: `stage_results` only holds the
  newest row per `(package, stage, target)` regardless of when it was written.
- Failure `reason` is often only `prior-failed` (a cached earlier failure), so the real
  cause lives in the log; that is why the excerpt exists.
- No `json` format: `make db-export FORMAT=json` already covers machine consumers.

## Testing

`tests/test_last_build.py`: a fixture DB with runs inside and outside the window;
newest-row resolution (a failure fixed by a later run is dropped); stage counts and
slowest ordering; the 20-line excerpt cap; pruned-log message; the `PACKAGE`/`TARGET`
filters; the empty-DB message; `md` link rendering.

## Status

Shipped.
