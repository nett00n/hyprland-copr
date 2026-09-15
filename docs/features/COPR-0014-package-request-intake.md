# COPR-0014. Request a new package via GitHub issue

**Tags:** #packages #intake

## User Story

As a user without repo write access, I want to request a package through a structured
GitHub issue form, so that the maintainer has everything needed to scaffold it without
a back-and-forth.

## Behavior

`.github/ISSUE_TEMPLATE/new_package.yml` provides a structured form (repo URL, build
system, notes) that feeds directly into the `add-new`/`scaffold-package` automation
(COPR-0001). `docs/package-requests.md` separately tracks a maintainer-curated
wishlist of candidate packages not yet requested as issues — "not tasks, not bugs,
just a wishlist".

## Implementation

- `.github/ISSUE_TEMPLATE/new_package.yml`, `.github/ISSUE_TEMPLATE/config.yml`.
- `docs/package-requests.md`.

## Quirks & Decisions

None currently tracked.

## Testing

### Human

- Open the issue template on GitHub; confirm required fields map cleanly onto
  `make add-new URL=...`'s inputs.

## Status

Implemented
