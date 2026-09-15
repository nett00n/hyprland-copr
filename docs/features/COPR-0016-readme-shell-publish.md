# COPR-0016. Auto-publish the README branding shell in CI

**Tags:** #ci #docs #publish

## User Story

As a maintainer, I want the README's branding shell (logo, description, News, Docs,
Support, License, People) refreshed on every push to `main`, so that it never goes
stale even though CI can't render the full build-status body.

## Behavior

`.github/workflows/publish-readme.yml` runs `make readme-shell` on every push to
`main` or manual dispatch, committing (`[skip ci]`) and pushing if anything changed.
`scripts/gen-readme-shell.py` splices `__header.j2`/`__footer.j2` into `README.md`/
`docs/README.copr.md` between existing `<!-- BEGIN: X -->`/`<!-- END: X -->` markers —
everything between the header and footer (the packages table, build status) is left
exactly as committed. `docs/full-report.md` isn't touched at all.

Safe by construction: CI has no `build-report.db` (gitignored, no build history), so
it can't run the full `make readme`; the shell-only path never touches the
packages/build-status region, so there's no path to an empty-package README landing
on `main` even from a from-scratch checkout.

## Implementation

- `scripts/gen-readme-shell.py`, `.github/workflows/publish-readme.yml`.

## Quirks & Decisions

None currently tracked (the contributor-rendering quirk affecting this template family
belongs to [COPR-0012](COPR-0012-docs-generation.md), BUG-0030).

## Testing

### Unit

- `tests/test_readme_content.py`.

### Human

- Push a branding-only change (`repo.yaml`, `blog/NEWS.md`) to `main`; confirm the CI
  workflow commits the regenerated shell with no packages-table diff.

## Status

Implemented
