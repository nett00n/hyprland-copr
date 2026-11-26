# COPR-0032. Fedora version rollover

**Tags:** #matrix #maintenance

## User Story

As a maintainer, I want one short, repeatable procedure (and as few places as possible
to touch) to add a newly released Fedora version to the build matrix, so that a release
day does not mean hunting for hardcoded versions across the Makefile, scripts, docs and
Copr gate.

## Behavior

Each version fact lives in exactly one place per language, and a test pins the two
sides together:

| Fact | Makefile | Python (`lib.paths` / `lib.yaml_utils`) |
| --- | --- | --- |
| Supported matrix | `SUPPORTED` | `SUPPORTED_FEDORA_VERSIONS` |
| Default `FEDORA_VERSION` (newest stable) | `DEFAULT_FEDORA_VERSION` | `DEFAULT_FEDORA_VERSION` |
| Canonical chroot (oldest supported; builds first, bumps release) | `CANONICAL_FEDORA_VERSION` | `CANONICAL_FEDORA_VERSION` |
| Version that is currently rawhide | - | `RAWHIDE_FEDORA_VERSION` |

Copr names the rolling chroot `fedora-rawhide-<arch>`, while local mock builds it as
`fedora-<N>-x86_64` (`mock-core-configs` symlinks `fedora-<N>` to rawhide until it
branches). `lib.copr` maps `fedora-rawhide-x86_64` to
`mock_chroot(RAWHIDE_FEDORA_VERSION)`, so the per-package Copr gate
([COPR-0007](COPR-0007-copr-submission.md)) treats it like any other chroot: a package
that failed locally on that version is held back. `fedora-rawhide-aarch64` stays
unverifiable, same as every aarch64 chroot ([COPR-0020](COPR-0020-aarch64-local-builds.md)).

### Rollover checklist (new version `N` released)

1. Add `N` to `SUPPORTED` and `SUPPORTED_FEDORA_VERSIONS`.
2. Bump `DEFAULT_FEDORA_VERSION` to the newest *stable* version (both sides).
3. Bump `RAWHIDE_FEDORA_VERSION` when rawhide becomes the next number.
4. Refresh the toolbox base image tag and digest
   ([COPR-0011](COPR-0011-toolbox-container.md)).
5. Extend every `fedora:` block that skips *all* versions with `N: skip: true`
   (`grep -n "skip: true" -B6 packages.yaml`), then run the matrix and fix or skip what
   breaks (a `BUGS.md` entry per skip).
6. Add the `Fedora N Ready` badge to `repo.yaml`, run `make readme`.
7. Dropping an EOL version is a separate change: remove it from `SUPPORTED`, move
   `CANONICAL_FEDORA_VERSION` to the new oldest, delete its `fedora:`/`%if` leftovers.

## Implementation

- `Makefile`: `SUPPORTED`, `DEFAULT_FEDORA_VERSION`, `CANONICAL_FEDORA_VERSION`;
  `container-volume-clean` compares against `DEFAULT_FEDORA_VERSION`, not a literal.
- `scripts/lib/paths.py`, `scripts/lib/yaml_utils.py`: the Python constants.
- Every `scripts/*.py` that reads `FEDORA_VERSION` falls back to
  `DEFAULT_FEDORA_VERSION`, never a literal.
- `scripts/lib/copr.py`: `_local_target()` used by `chroot_coverage()`.

## Quirks & Decisions

- Decision: canonical is the *oldest* supported version, not the default. The matrix
  keeps building it first, as it does today.
- Decision: rawhide is not a matrix entry of its own. It is the newest numbered
  version, so mock, build_db and local repos keep the numeric `fedora-<N>` key.
- Quirk: rawhide's `fc<N>` dist tag is valid for the foreign-dist preflight
  (`repo_preflight.target_dist_tag`) while `N` is rawhide; it becomes the stable tag
  later without any change.
- Quirk (fixed): a numbered version that is still rawhide gets a symlinked mock config
  whose `root` is `fedora-rawhide-<arch>`; mock's resultdir follows that, not `-r`.
  `stage-mock` passes `--resultdir` explicitly
  ([COPR-0006](COPR-0006-local-mock-builds.md)); BUG-0122 tracks the silent success.
- Quirk: the container's Python minor version must match the host's, because
  `.venv` is shared between them (bind-mounted at `/work/.venv`); a base-image bump
  that changes the Python minor needs the venv rebuilt.
- Quirk (fixed): `container-volume-clean` used the literal `"44"` as its "no version
  given" sentinel and would have silently misbehaved after a default bump.

## Testing

### Unit

- `tests/test_fedora_versions.py`: Makefile and Python constants agree; canonical is
  `min(SUPPORTED)`, rawhide is `max(SUPPORTED)`, default is in `SUPPORTED`; no script
  hardcodes a `FEDORA_VERSION` fallback.
- `tests/test_copr.py`: `fedora-rawhide-x86_64` resolves to the local rawhide-version
  row; `fedora-rawhide-aarch64` stays unverifiable.

## Status

Implemented
