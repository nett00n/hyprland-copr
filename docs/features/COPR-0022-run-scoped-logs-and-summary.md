# COPR-0022. Run-scoped logs and a durable nightly summary

**Tags:** #daily #diagnostics #logs

## User Story

As a maintainer, I want each night's build logs kept under a run identifier and a
summary of what happened committed somewhere durable, so that a failure from two
nights ago isn't simply gone by the time I look for it.

## Behavior

Today `get_package_log_dir()` resolves to a flat `logs/build/<pkg>/` with no run
identifier, and `update-daily` `rmtree`s that tree before each night's run — so a
failure from an earlier run leaves nothing to diff a flaky failure against. Logs also
lack a distro/version segment, so an f43 and f44 build of the same package overwrite
each other's logs. And nothing beyond a commit-message timestamp reports what a given
night's run actually did.

Planned: nest logs under both a run identifier and the target chroot —
`logs/<run_id>/<distro>-<version>/<package>/` — with a retention/prune policy in the
same change (unbounded per-run dirs would otherwise grow `logs/` forever), landed
together with the distro/version restructure rather than doing the path layout twice.
`pkg-log-analysis.py --output <file>` then becomes a durable nightly summary that links
back to the exact per-run, per-os-version log instead of whatever happens to be on
disk right now.

## Implementation (planned)

- `lib/paths.py` (`get_package_log_dir()` and friends).
- `scripts/pkg-log-analysis.py` `--output` mode.
- `stage-mock.py`'s `copy_mock_results()` — live-tailing mock's resultdir via a
  bind-mount is a separable, cheaper follow-up, independent of the path-layout change.

## Quirks & Decisions

- Open: `update-daily`'s summary step is blocked on the run-scoped log paths landing
  first — without them there's nothing stable to link a summary to.

## Testing (planned)

- Unit: `get_package_log_dir()` for a given `(run_id, distro, version, package)`
  resolves without collision across two chroots of the same package.
- Integration: two consecutive `update-daily` runs leave both nights' logs on disk,
  each linked from its own summary.

## Status

Planned
