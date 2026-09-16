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

## Implementation

- `scripts/update-versions.py`, `lib/version.py`.
- Runs first in `make update-daily` (COPR-0003), before the quality gate.

## Quirks & Decisions

- Quirk: fetches 45+ submodules serially, and 10 separate warn-and-continue sites
  print individual failures to stderr with nothing aggregated — a single `git fetch`
  failure is invisible in the stdout summary, so a package can silently sit on a stale
  version indefinitely.
  Proposed: aggregate the warn-and-continue sites into one failure report. (BUG-0100)
- Quirk: the per-submodule pull/fetch loop runs serially with no concurrency.
  Proposed: add `ThreadPoolExecutor`-based concurrency, once the aggregate-reporting
  fix above can show what broke; split out separately since it's a different risk
  profile (shared `.git/modules` state). (BUG-0101)
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

- `tests/test_update_versions.py`, `tests/test_version.py`.

## Status

Implemented
