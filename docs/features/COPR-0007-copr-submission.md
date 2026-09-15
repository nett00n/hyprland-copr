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

## Implementation

- `scripts/stage-copr.py`, `scripts/lib/copr.py`
  (`ineligible_packages()`/`block_transitive_dependents()`/`blackout_chroots()`/
  `poll_copr_status()`).
- Requires `copr-cli` configured with `~/.config/copr`.

## Quirks & Decisions

- Quirk: any package resubmitted tonight publishes as Copr state `unknown` in the
  generated docs — `readme`/`copr-description` run seconds after an async
  `--nowait` submit, one poll too early for whatever was just resubmitted.
  Open: needs a design decision (poll again before docs regenerate? delay the docs
  step?).
- Quirk: copr rows are keyed by one local `target`, but Copr fans a submission out to
  its own chroot set — a real per-chroot matrix view needs `stage_results` (or a
  separate table) keyed by the Copr chroot, not the local one.
  Proposed: see [COPR-0021](COPR-0021-copr-chroot-matrix.md) (Planned).
- Quirk: aarch64 chroots always report "not verifiable locally" (no cross-arch build
  path exists) and can never satisfy the per-chroot coverage gate.
  Open: see [COPR-0020](COPR-0020-aarch64-local-builds.md) (Planned).

## Testing

### Unit

- `tests/test_copr.py`, `tests/test_pipeline_copr_stage_utils.py`.

### Integration

- `tests/integration/test_entry_points.py`, `tests/integration/test_make_targets.py`.

## Status

Implemented
