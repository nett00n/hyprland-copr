# COPR-0005. Generate RPM spec files from packages.yaml

**Tags:** #packaging #spec

## User Story

As a maintainer, I want the RPM spec file for every package generated from one shared
template and `packages.yaml`, so that packaging conventions stay consistent across 49
packages without hand-editing each spec.

## Behavior

`make stage-spec PACKAGE=<name>` renders `packages/<name>/<name>.spec` from
`templates/spec.j2` and the package's `packages.yaml` entry — sources, `build_requires`,
`depends_on`, `files:`, release, and (for Go/Rust) the vendor tarball extraction. The
generated spec is committed and human-editable, but the source of truth for the next
regeneration is always `packages.yaml`.

Per [COPR-0018](COPR-0018-single-spec-single-srpm.md), one spec is generated once and
reused across every chroot in a matrix build — no per-`FEDORA_VERSION` content. A
per-version difference is written as a literal `%if 0%{?fedora} == N ... %endif`
conditional directly in `build.prep`/`commands`/`install` (see docs/packaging.md
"Per-Fedora-version spec differences").

An edit to `templates/spec.j2`, `scripts/stage-spec.py`, or `scripts/lib/spec_utils.py`
(the generator itself) does not force a rebuild: every package's spec/vendor/srpm/mock
cache stays a hit, and the packages whose spec was actually generated from an older
template or generator version are reported (`stage-show-plan`/`gen-report`) as
`stale-template`/`stale-generator` instead (#BUG-0057, #BUG-0058).

## Implementation

- `scripts/stage-spec.py`, `templates/spec.j2`.
- `scripts/gen-spec.py` is a separate, older generator with its own duplicated logic
  (see Quirks) — `stage-spec.py` is the one the pipeline actually uses.

## Quirks & Decisions

- Quirk: `gen-spec.py` (446 lines) duplicates `lib/github.py` and
  `lib.config.get_packager` almost verbatim, has no Makefile target, and is unused
  except by its own test.
  Proposed: check whether `build_context()` has spec-rendering logic `stage-spec.py`
  lacks, then remove or replace with lib calls. (BUG-0074)

## Testing

### Unit

- `tests/test_gen_spec.py`, `tests/test_spec_utils.py`.

## Status

Implemented
