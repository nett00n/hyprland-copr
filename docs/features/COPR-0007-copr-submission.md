# COPR-0007. Submit builds to Copr

**Tags:** #copr #publish

## User Story

As a maintainer, I want to submit a verified build to Copr and have the project
description/install docs stay current automatically, so that Copr always reflects
what's actually been built and tested.

## Behavior

`make stage-copr PACKAGE=<name> COPR_REPO=<project>` submits the canonical target's
SRPM to Copr (async `--nowait` by default; `SYNCHRONOUS_COPR_BUILD=true` waits).
Submission is gated **per package**, not all-or-nothing: a package not yet verified
(or deliberately skipped) on every locally-buildable chroot, and its transitive
dependents, are held back individually with a reason naming the chroot — everything
else in the run still submits. If a locally-buildable chroot has zero verified/skipped
packages at all (a "blackout" chroot — e.g. a brand-new Fedora version with no
coverage yet), the whole submission fails loudly instead of silently exiting 0 with
nothing submitted. `REQUIRE_CHROOT_COVERAGE=true` additionally blocks the whole
submission on any gap; `ALLOW_EMPTY_COPR_SUBMISSION=true` opts out of the blackout
failure for a deliberate no-op run.

After the matrix submits, `make copr-wait` bounds a retry poll
(`lib.copr.poll_copr_status(..., deadline_s=, interval_s=)`) for up to
`COPR_POLL_TIMEOUT` seconds (default 1800), re-checking every `COPR_POLL_INTERVAL`
seconds (default 30), so the docs generated right after (`make readme`) render each
resubmitted package's real state instead of the stale `unknown` it starts async
submission with (#BUG-0039). A package still non-terminal at the deadline keeps
`unknown` in this run's docs and resolves on the *next* run's existing pre-submit
poll (`full-cycle.py`'s `poll_copr_status()` call before resubmitting). `copr-wait`
always exits 0 — a build still running at the deadline is not a nightly failure.

## Implementation

- `scripts/stage-copr.py`, `scripts/copr-wait.py`, `scripts/lib/copr.py`
  (`ineligible_packages()`/`block_transitive_dependents()`/`blackout_chroots()`/
  `poll_copr_status()`).
- Requires `copr-cli` configured with `~/.config/copr`.

## Quirks & Decisions

- Decision (#BUG-0039): async submission is kept as-is (making it synchronous would
  serialize dozens of independent Copr builds behind each other); instead
  `_full-cycle-matrix` runs `copr-wait` right after `stage-copr`, bounding the
  retry with a deadline rather than blocking submission itself.
- Quirk: `stage-copr`'s Makefile recipe did not forward `SYNCHRONOUS_COPR_BUILD`
  into the container (unlike `_full-cycle`), so `.env`'s
  `SYNCHRONOUS_COPR_BUILD=true` never reached it in the nightly path — submission
  was silently always async regardless of that setting. Fixed alongside #BUG-0039.
- Quirk: copr rows are keyed by one local `target`, but Copr fans a submission out to
  its own chroot set — a real per-chroot matrix view needs `stage_results` (or a
  separate table) keyed by the Copr chroot, not the local one.
  Proposed: see [COPR-0021](COPR-0021-copr-chroot-matrix.md) (Planned).
- Quirk: aarch64 chroots always report "not verifiable locally" (no cross-arch build
  path exists) and can never satisfy the per-chroot coverage gate.
  Open: see [COPR-0020](COPR-0020-aarch64-local-builds.md) (Planned).

## Testing

### Unit

- `tests/test_copr.py` (incl. `poll_copr_status`'s bounded-retry `deadline_s`/
  `interval_s` behavior), `tests/test_pipeline_copr_stage_utils.py`.

### Integration

- `tests/integration/test_entry_points.py`, `tests/integration/test_make_targets.py`.

## Status

Implemented
