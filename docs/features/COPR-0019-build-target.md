# COPR-0019. Distro/arch-agnostic build target

**Tags:** #matrix #build

## User Story

As a maintainer wanting to support a non-Fedora distro or a non-x86_64 arch, I want
the build target to be a real `(distro, version, arch)` triple instead of a bare
`FEDORA_VERSION` env var, so that the pipeline isn't structurally Fedora+x86_64-only.

## Behavior

`FEDORA_VERSION` becomes one case of a general `TARGET` (or `DISTRO`+`ARCH`) knob.
`SUPPORTED`, `mock_chroot()`, the `Containerfile` `FROM`, and `lib/paths.py`'s
module-level `DISTRO`/`ARCH` constants all currently hardcode Fedora — this is the
keystone item other matrix work depends on. `MOCK_CHROOT` already exists as a per-run
override read by every stage, so an arbitrary chroot can be forced in today, but
`DISTRO`/`ARCH` stay wrong and image/volume names don't follow.

Once landed:

- `packages.yaml` gets distro-agnostic override keys (today: exactly one `fedora:`
  block, under `hyprland` — nearly free to migrate now versus at 20 blocks).
- `lib/version.py`'s `nvr()` stops hardcoding the `.fcNN` dist tag (CentOS wants
  `.el10`); this also resolves the cosmetic SRPM/build-report.db dist-tag mismatch
  noted in [COPR-0018](COPR-0018-single-spec-single-srpm.md) and
  [COPR-0008](COPR-0008-release-numbering.md).
- The `mock-cache-$(FEDORA_VERSION)`/`mock-root-$(FEDORA_VERSION)` podman volumes get
  arch-keyed too, so two arches stop clobbering each other's cache — a rename that
  orphans every existing volume on every dev machine, paired with a
  `container-volume-clean` migration note.

## Implementation (planned)

- `lib/paths.py` (`DISTRO`/`ARCH`/`mock_chroot()`), `Containerfile` `FROM`,
  `Makefile` volume naming, `lib/version.py` `nvr()`, `lib/validation.py` override-key
  handling.

## Quirks & Decisions

- Open: this is explicitly sequenced before aarch64 support
  ([COPR-0020](COPR-0020-aarch64-local-builds.md)) — doing aarch64 first means doing
  the `DISTRO`/`ARCH` constant work twice.

## Testing (planned)

- Unit: `lib/paths.py`'s target-resolution functions for a non-Fedora, non-x86_64
  triple.
- Integration: a `MOCK_CHROOT` override for a hypothetical CentOS/aarch64 target runs
  end to end without editing source constants.

## Status

Planned
