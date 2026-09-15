# COPR-0023. Upstream source signature verification

**Tags:** #security #provenance

## User Story

As a maintainer, I want an upstream source's signature (not just its checksum)
verified before it's packaged, so that a compromised mirror or a maliciously retagged
release is caught even if the tamper happens before `sources.lock.yaml` first records
its hash.

## Behavior

`sources.lock.yaml` (see docs/packaging.md "Source verification") already pins a
sha256 per remote source and is TOFU (trust-on-first-use) — it proves bytes haven't
changed since first recorded, not that upstream was honest at record time. It checks
no signature.

Two distinct, deliberately deferred mechanisms:

- **GPG/detached-signature verification**: a per-package `source.gpg_key` plus
  fetching the matching `.asc`/`.sig` next to the archive, and a repo-local keyring.
  Moot for the current package set — 43/45 sources are GitHub auto-generated tag
  archives, which GitHub does not sign. **Recommend parking** until a genuinely
  signed upstream release shows up; out of scope even then: which keyserver,
  TOFU-vs-pinned key trust, and revocation.
- **Signed git tags**: `git tag -v <tag>` inside the submodule checkout, for upstreams
  that sign tags (not the same as a signed release tarball). The old submodule-init
  blocker for this is gone — `submodules-update` and `preflight_autoheal()` already
  init missing submodules unconditionally; the only remaining substance is that
  `git tag -v` verification itself isn't implemented.

## Implementation (planned)

- `lib/source_lock.py` (verification hook point).
- `scripts/update-versions.py` (tag-verification call site, for the `git tag -v` half).

## Quirks & Decisions

- Open: GPG/detached-signature verification is explicitly a decision to park, not a
  task to schedule — revisit only when a package with a genuinely signed upstream
  release appears.

## Testing (planned)

- Unit: `git tag -v` verification against a known-good and a known-bad (unsigned or
  tampered) tag.

## Status

Planned
