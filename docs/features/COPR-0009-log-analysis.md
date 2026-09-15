# COPR-0009. Analyze build logs and surface actionable errors

**Tags:** #build #diagnostics

## User Story

As a maintainer with a failed build, I want the log scanned for the actual cause, so
that I don't have to read a multi-thousand-line mock/rpmbuild log by hand.

## Behavior

`make stage-log-analyze PACKAGE=<name>` reports missing dependencies, incompatible
plugins, missing source files, compile errors with line references, unsatisfiable
buildroot transactions, CMake `FetchContent` network-fallback failures, gmake "No rule
to make target" errors, and (for Copr) which chroots failed vs. succeeded — instead of
the generic "Bad exit status" every unrecognized failure would otherwise print.

## Implementation

- `lib/log_analysis.py` (regex-driven rule set), `scripts/pkg-log-analysis.py`
  (multi-package CLI, also run automatically by `update-daily` after `readme`).

## Quirks & Decisions

- Quirk: 1257 lines of ~41 copy-pasted `if m: issues.append(...); continue` blocks
  from hand-written regexes.
  Proposed: a data table of `(regex, formatter)` pairs would cut it by half or more.
  Well covered by existing tests, making this an unusually safe refactor. (BUG-0083)
- Quirk: `scripts/pkg-log-analysis.py` imports eight underscore-prefixed "private"
  functions directly from `lib.log_analysis`, and redefines `HIGHLIGHT_PREFIX` locally
  as a third copy of that constant.
  Proposed: make the functions public API, or move this script's logic into `lib/` —
  best done together with the regex-table refactor above, since it changes these
  function boundaries anyway. (BUG-0087)
- Quirk: analysis output only goes to whatever captures `update-daily`'s stdout (cron
  mail, if configured) — no durable nightly summary artifact.
  Proposed: see [COPR-0022](COPR-0022-run-scoped-logs-and-summary.md) (Planned).

## Testing

### Unit

- `tests/test_log_analysis.py`, `tests/test_log_analysis_gaps.py`,
  `tests/test_pkg_log_analysis.py`.

## Status

Implemented
