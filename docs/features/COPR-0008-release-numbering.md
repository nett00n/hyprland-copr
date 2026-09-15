# COPR-0008. Auto-manage RPM release numbers

**Tags:** #packaging #release

## User Story

As a maintainer, I want each package's RPM `release` field to advance correctly on
its own, so that I never have to remember whether a rebuild needs a bumped release or
manually track cascades through dependents.

## Behavior

| Situation | `release` action |
| --- | --- |
| Version changed | reset to `1` |
| Content differs, same version | increment by 1 |
| Content unchanged, no force, no dependency cascade | no change |
| Force-run, or a `depends_on` dependency was rebuilt | increment by 1, cascades to every dependent |

Content hash excludes `release` itself, so a release-only edit never re-triggers
itself. Manual override: `make set-release PACKAGE=<name> RELEASE=<n> LOCK=1` (`LOCK=1`
skips further auto-management until removed); `release_lock: true` in `packages.yaml`
does the same declaratively.

## Implementation

- `lib/yaml_utils.update_package_releases()`, called from `full-cycle`'s pre-build
  step; `lib/version.py` for NVR computation.
- `update-versions.py` sets `release: 0` on a version bump, signaling the reset.

## Quirks & Decisions

- Quirk: `full-cycle-matrix` used to bump a package's release once per matrix chroot
  (three times a night). Fixed: only the canonical chroot's `full-cycle` call performs
  the release step (`SKIP_RELEASE_BUMP=true` on every other chroot) — see
  docs/CHANGELOG.md 2026-09-08 (closed #BUG-0049).
- Quirk: the physical SRPM's own dist tag is always stamped from the container's
  pinned Fedora base (`.fc43`), regardless of which `FEDORA_VERSION` a build targets —
  `build-report.db`'s recorded `version=...fc45` disagrees with the literal filename.
  Cosmetic only: `mock --rebuild`/Copr both re-expand `%{?dist}` from the target
  chroot's own macros at build time, so binary RPMs are correctly tagged regardless.
  Proposed: fold into the distro-agnostic `nvr()` rework in
  [COPR-0019](COPR-0019-build-target.md) (Planned) once it lands.

## Testing

### Unit

- `tests/test_release_tracking.py`, `tests/test_set_package_release.py`,
  `tests/test_version.py`.

## Status

Implemented
