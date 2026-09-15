# COPR-0021. Per-chroot Copr rows and a package × target matrix report

**Tags:** #matrix #copr #reporting

## User Story

As a maintainer, I want Copr build state tracked per actual Copr chroot (not per one
local target) and visualized as a package × target grid, so that I can see coverage
across the whole build matrix at a glance instead of cross-referencing chroot logs by
hand.

## Behavior

Today `stage-copr.py` resolves a single local `target` per run and stores one copr row
for it, even though Copr fans a submission out to its own chroot set. The per-package
Copr gate ([COPR-0007](COPR-0007-copr-submission.md)'s `ineligible_packages()`) already
sidesteps this by reading per-chroot *mock* rows instead, which are correctly
per-chroot — but the copr stage's own row, `fetch_failed_chroot_logs`, and
`print_chroot_coverage` still don't have a real per-Copr-chroot dimension.

Once fixed: `stage_results` (or a new table) gains a `copr_chroot` dimension, and
`gen-report`/its templates render a package × target grid instead of assuming one
target per report — currently blocked on this, since a grid needs the column to mean
something.

## Implementation (planned)

- Schema change to `stage_results` (or a sibling table), reusing the shape of the
  `sha256`/`arch` migration in [COPR-0015](COPR-0015-build-state-db.md) (BUG-0061,
  BUG-0065) rather than bumping the schema twice.
- `stage-copr.py`'s `fetch_failed_chroot_logs`/`print_chroot_coverage`.
- `gen-report.py`, `templates/full-report.md.j2`.

## Quirks & Decisions

None yet — not started.

## Testing (planned)

- Unit: a copr row keyed by `(package, copr_chroot)` distinct from the local `target`.
- Integration: `gen-report`'s matrix view renders correctly with a package verified on
  some chroots and not others.

## Status

Planned
