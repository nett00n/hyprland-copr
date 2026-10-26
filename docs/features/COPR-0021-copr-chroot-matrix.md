# COPR-0021. Per-chroot Copr rows

**Tags:** #matrix #copr

## User Story

As a maintainer, I want Copr build state tracked per actual Copr chroot (not per one
local target), so that I can see coverage across the whole build matrix instead of
cross-referencing chroot logs by hand.

## Behavior

Today `stage-copr.py` resolves a single local `target` per run and stores one copr row
for it, even though Copr fans a submission out to its own chroot set. The per-package
Copr gate ([COPR-0007](COPR-0007-copr-submission.md)'s `ineligible_packages()`) already
sidesteps this by reading per-chroot *mock* rows instead, which are correctly
per-chroot — but the copr stage's own row, `fetch_failed_chroot_logs`, and
`print_chroot_coverage` still don't have a real per-Copr-chroot dimension.

Once fixed: `stage_results` (or a new table) gains a `copr_chroot` dimension. A
rendered package × target grid was originally part of this item; it was dropped along
with the markdown build reports (see [COPR-0012](COPR-0012-docs-generation.md)).

## Implementation (planned)

- Schema change to `stage_results` (or a sibling table), reusing the shape of the
  `sha256`/`arch` migration in [COPR-0015](COPR-0015-build-state-db.md) (BUG-0061,
  BUG-0065) rather than bumping the schema twice.
- `stage-copr.py`'s `fetch_failed_chroot_logs`/`print_chroot_coverage`.

## Quirks & Decisions

None yet — not started.

## Testing (planned)

- Unit: a copr row keyed by `(package, copr_chroot)` distinct from the local `target`.

## Status

Planned
