# COPR-0018. Generate the spec and SRPM once, reuse across every chroot

**Tags:** #build #matrix #spec #srpm

## User Story

As a maintainer running a matrix build, I want the spec and SRPM built exactly once
and reused across every Fedora version, so that a 3x chroot matrix doesn't also mean
3x redundant spec/SRPM generation.

## Behavior

The single container image and its shared `rpmbuild` podman volume (COPR-0011) make
this true by construction — there is only ever one `~/rpmbuild/SRPMS` to build into or
read from, for any chroot. A per-Fedora-version spec difference is written directly in
`packages.yaml`'s `build.prep`/`commands`/`install` as a literal
`%if 0%{?fedora} == N ... %endif` conditional — rpm evaluates it per chroot when
`mock`/Copr rebuild the SRPM — rather than synthesized by merging a `fedora:` override
block. That block now only supports `skip`; any other key is rejected by
`lib.validation` (shared by `validate-packages.py` and `stage-validate.py`).

## Implementation

- `scripts/stage-srpm.py`, `scripts/lib/paths.py` (shared `rpmbuild` volume).
- `lib.yaml_utils.apply_os_overrides()` (resolves `skip` only).

## Quirks & Decisions

- Quirk: the physical SRPM's own dist tag is stamped from the container's pinned base
  (`.fc43`) regardless of target `FEDORA_VERSION`, disagreeing cosmetically with
  `build-report.db`'s target-computed label. Not a correctness bug — `mock`/Copr both
  re-expand `%{?dist}` from the chroot's own macros at build time.
  Proposed: fold into [COPR-0019](COPR-0019-build-target.md) (Planned)'s `nvr()`
  rework once distro-agnostic dist tags land.

## Testing

### Unit

- `tests/test_stage_srpm.py`.

### Integration

- `tests/integration/test_entry_points.py`, `tests/integration/test_cache_pipeline.py`.

## Status

Implemented
