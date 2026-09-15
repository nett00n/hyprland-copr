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
- Quirk: no `KeyboardInterrupt` handling — the longest-lived script in the nightly run
  (serially fetching 45+ submodules over the network) has no clean Ctrl+C exit.
  Proposed: add the same `except KeyboardInterrupt: sys.exit(130)` wrapper every other
  top-level script already has. (BUG-0072)
- Quirk: a `depends_on` package on `latest-commit` can silently outrun a tag-pinned
  sibling's API (e.g. `hyprland-plugins` tracking `main` past what pinned `Hyprland`
  ships) — nothing flags this drift before mock fails.
  Open: no automated check for the class exists yet across any other package pair.
  (BUG-0056)

## Testing

### Unit

- `tests/test_update_versions.py`, `tests/test_version.py`.

## Status

Implemented
