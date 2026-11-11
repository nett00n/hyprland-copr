# COPR-0012. Render the READMEs from the repo's source of truth

**Tags:** #docs

## User Story

As a maintainer, I want `README.md` and the Copr project readme regenerated from
`packages.yaml`, `groups.yaml`, `repo.yaml`, `docs/NEWS.md` and git history, so that
published docs never drift from hand-edited text and rendering them needs no build
history.

## Behavior

`make readme` renders `README.md` (`templates/readme-github.md.j2`) and
`docs/README.copr.md` (`templates/readme-copr.md.j2`) in one container run. It reads
no `build-report.db` and polls nothing: there is no markdown build report any more
(`docs/full-report.md` and the README "Build Status" section were removed — they were
not usable in this implementation). Build state lives in `build-report.db`, the stage
logs and `docs/nightly-summary.md`.

The package list is built from `groups.yaml`: a `packages:` entry is listed only if it
exists in `packages.yaml` (its `summary` is the description shown), and
`packages_from_global_repo` entries are listed as given.

`docs/README.copr.md` is deliberately minimal because it is shown on the COPR project
page, which cannot render HTML comments: logo, the badge lines of `repo.description`
(its prose is left out), the packages list, the Support section, and News last. No
generated Markdown or template contains HTML comments.

`make check-docs-drift` (#BUG-0031) verifies the committed READMEs still match their
inputs: it re-renders both from the yaml files, NEWS and git history into a scratch
dir and diffs against the committed files, failing on any difference. Contributors
come from git history, so CI checks out with `fetch-depth: 0`.

In `_update-daily`, `readme` runs after `copr-wait` (see
[COPR-0007](COPR-0007-copr-submission.md)); the README no longer shows build state, so
the order only matters for the logs `copr-wait` fetches.

## Implementation

- `scripts/gen-report.py` (`--format github|copr`, `--output`, both repeatable and
  paired positionally; `collect_groups()` builds the package list).
- `repo.yaml` controls branding/layout (badge style, News feed limit, per-section
  visibility).

## Quirks & Decisions

- Decision: `_contributors.j2` renders each entry with an inline `{{ ... if ... else ... }}`
  expression instead of an `{% if %}` block tag, because `trim_blocks=True` would eat
  the newline after `{% endif %}` and concatenate entries onto one line. Contributors
  are deduped by commit email (not `user.name`), so one person committing under two
  names renders once, under their most recent name. (BUG-0030)
- Decision: a `groups.yaml` package missing from `packages.yaml` is skipped silently
  (e.g. a group entry for a package that was never added), matching the old behavior
  where it was skipped for lacking build rows.
- Decision: the markdown build reports were dropped rather than fixed; the
  `docs/db-snapshot.yaml` export that only existed to render them in CI went with them.

## Testing

### Unit

- `tests/test_gen_report.py` (incl. `collect_groups`), `tests/test_readme_content.py`.

### Integration

- `make check-docs-drift`: negative control verified manually (hand-edited
  `README.md`, confirmed the diff was caught and the target exits non-zero) — no
  automated test for the Makefile target itself, since it shells out to the real repo
  tree rather than a fixture.

## Status

Implemented
