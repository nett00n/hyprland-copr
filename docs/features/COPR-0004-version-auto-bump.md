# COPR-0004. Auto-bump package versions from upstream

**Tags:** #versioning #upstream

## User Story

As a maintainer, I want each package's version to advance from its upstream git repo
automatically, per a policy I set once, so that I don't have to manually track and
bump 49 packages' versions.

## Behavior

`make update-versions` fetches the latest tag/commit for every submodule and rewrites
`packages.yaml`'s `version`/`source.commit` fields, according to each package's own
`auto_update.release_type`:

| Type | Behavior | Version format |
| --- | --- | --- |
| `latest-version` | latest semver tag only | `1.2.3` |
| `latest-tag` | latest version-like tag, any component count | `1.9` |
| `latest-commit` | latest commit on branch | `1.2.3^20240101gitabc1234` |
| `pinned-version` | pins to tag `v<version>`; no updates | - |
| `pinned-commit` | pins to `source.commit.full`; no updates | - |
| `pinned-tag` | pins to a specific non-semver tag | `0.53.0^20240101gitabc1234` |
| *(absent)* | try semver, fall back to commit | `1.2.3` or `0^20240101gitabc1234` |

Bumping a version also resets that package's `release: 0`, signaling the next build to
reset the release counter (see [COPR-0008](COPR-0008-release-numbering.md)).

`scripts/update-versions.py` handles Ctrl+C cleanly: `except KeyboardInterrupt:
sys.exit(130)`, same as the rest of the pipeline. (#BUG-0072)

`make validate-packages` warns (offline, no network) when a `latest-commit`/
`pinned-commit` package's `source.commit.date` is newer than a tag-pinned
`depends_on` sibling's pinned tag date — the drift class that broke
`hyprland-plugins` against `Hyprland` across all three chroots (runs 76–78) before
mock caught it. (#BUG-0056)

Every warn-and-continue site along the way (a submodule that doesn't exist, a
`git fetch`/`switch`/`checkout` failure, an unresolved pin, a `fetch_tags()`
failure/timeout, no version-like tag found, an unknown `release_type`, a
conflicting pin) also collects a `Failure(scope, kind, detail)` alongside its
existing stderr print. At the end of the run:

- an aggregated block prints to stdout after the YAML summary, grouped by
  `kind`, so a run with one real outage doesn't scroll past unnoticed among
  routine per-package lines;
- when non-empty, the same report is written to
  `logs/.update-versions-failures.md` (removed when there are no failures, so
  a stale file from a previous failing run can never be read as tonight's);
  `scripts/pkg-log-analysis.py` folds it into `docs/nightly-summary.md`'s
  `## Upstream version refresh` section when `make stage-log-analyze` runs
  (#COPR-0022);
- `_update-daily`'s closing banner echoes the failure count next to the
  existing "N package(s) updated tonight" line.

`make update-versions` still exits 0 when failures are collected: `Makefile`'s
`_update-daily` runs it as `$(MAKE) update-versions || exit 1`, so a non-zero
exit would abort the entire nightly over one flaky remote. Visibility, not
fatality — see `_update-daily`'s pattern for `full-cycle-matrix` (recorded via
`logs/.update-daily-failed`, not fatal either). (#BUG-0100)

## Implementation

- `scripts/update-versions.py`, `lib/version.py`, `lib/gitmodules.py` (`fetch_tags()`).
- Runs first in `make update-daily` (COPR-0003), before the quality gate.

## Quirks & Decisions

- Decision: every warn-and-continue site now also appends a `Failure` to an
  in-process list, rendered as one aggregated block (stdout) and one durable
  Markdown sentinel (`logs/.update-versions-failures.md`, folded into
  `docs/nightly-summary.md`) at the end of the run, instead of only ever
  scrolling past on stderr. The exit code stays 0 on partial failure — see
  `## Behavior` above for why. (BUG-0100, closed)
- Decision: `lib.gitmodules.fetch_tags()` used to return a bare `list[str]`,
  so a failed/timed-out `git ls-remote` and a genuinely tagless upstream were
  both `[]` — indistinguishable, and the single most common real network
  failure for tag-based packages was silently swallowed. It now returns
  `TagFetch(tags, error)`; `error` is non-`None` only on an actual fetch
  failure. (BUG-0100, closed)
- Quirk: the per-submodule pull/fetch loop runs serially with no concurrency.
  Proposed: add `ThreadPoolExecutor`-based concurrency, now that the
  aggregate-reporting fix above can show what broke; split out separately
  since it's a different risk profile (shared `.git/modules` state). (BUG-0101)
- `update-versions.py` now exits cleanly (130) on Ctrl+C instead of a raw traceback.
  (BUG-0072, closed)
- Decision: the drift check (`lib.validation.validate_dependency_drift()`) is
  offline and degrading — it reads only local submodule git state via the existing
  `lib.gitmodules.get_tag_commit()`, and skips silently (no warning) when a
  submodule is uninitialized or the tag isn't fetched locally, so CI and fresh
  clones stay green. It warns rather than errors: a commit-tracked package being
  ahead of a pinned sibling is common and often correct — the point is making the
  drift visible, not blocking on it. (BUG-0056, closed)

## Testing

### Unit

- `tests/test_update_versions.py`, `tests/test_version.py`, `tests/test_gitmodules.py`
  (`TagFetch`), `tests/test_pkg_log_analysis.py` (folding the failure report into
  `docs/nightly-summary.md`).

## Status

Implemented
