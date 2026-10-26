# COPR-0016. Auto-publish the READMEs in CI

**Tags:** #ci #docs #publish

## User Story

As a maintainer, I want the READMEs refreshed on every push to `main`, so that News,
the packages list and the branding never go stale between nightly runs.

## Behavior

`.github/workflows/publish-readme.yml` runs `make readme NO_CONTAINER=1` on every push
to `main` (currently commented out in the workflow, so manual dispatch only), committing (`[skip ci]`) and pushing `README.md` and
`docs/README.copr.md` if anything changed.

Safe by construction: the READMEs are rendered only from committed inputs
(`packages.yaml`, `groups.yaml`, `repo.yaml`, `docs/NEWS.md`, git history — see
[COPR-0012](COPR-0012-docs-generation.md)), so CI needs no `build-report.db` and a
from-scratch checkout renders the same files as a local run. The earlier
marker-splicing shell refresh (`gen-readme-shell.py`) is gone: it depended on
`<!-- BEGIN/END -->` comments, which COPR cannot render.

## Implementation

- `.github/workflows/publish-readme.yml`, `make readme`.

## Quirks & Decisions

None currently tracked (the contributor-rendering quirk affecting this template family
belongs to [COPR-0012](COPR-0012-docs-generation.md), BUG-0030).

## Testing

### Unit

- `tests/test_readme_content.py`, `tests/test_gen_report.py`.

### Human

- Push a News-only change (`docs/NEWS.md`) to `main`; confirm the CI workflow commits
  the regenerated READMEs with no other diff.

## Status

Implemented
