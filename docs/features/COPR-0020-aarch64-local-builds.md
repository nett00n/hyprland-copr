# COPR-0020. aarch64 local build support

**Tags:** #matrix #build #arch

## User Story

As a maintainer, I want aarch64 builds verifiable locally before Copr submission, so
that the per-chroot coverage gate ([COPR-0007](COPR-0007-copr-submission.md)) can
actually pass for aarch64 instead of permanently reporting "not verifiable locally".

## Behavior

aarch64 builds need qemu-user-static binfmt registration or a native ARM runner —
`mock --forcearch` alone is not enough for a real cross-arch build. Zero
`qemu`/`binfmt`/`forcearch` references exist in the repo today; the only aarch64
awareness is Copr-reporting code giving up with "not verifiable locally". Mostly a
multi-day infra decision (host binfmt registration, or a CI runner), not primarily a
code change — and it depends on [COPR-0019](COPR-0019-build-target.md) landing first,
since `DISTRO`/`ARCH` are still hardcoded constants until then.

Once local aarch64 coverage exists, `BUG-0018`'s residual (aarch64 chroots
permanently reporting "not verifiable locally") closes on its own, and general ARM64
local build support becomes available as a byproduct.

## Implementation (planned)

- Host or CI-runner binfmt/qemu-user-static setup (infra, not repo code).
- `lib/copr.py` chroot-coverage logic, once a real local aarch64 verdict exists.

## Quirks & Decisions

- Open: sequenced after [COPR-0019](COPR-0019-build-target.md) deliberately — doing
  this first means doing the `DISTRO`/`ARCH` constant work twice.

## Testing (planned)

- Integration: an aarch64 `mock -r` build (via binfmt or a native runner) reaches
  `verified` in the local coverage table, and the Copr submission gate for an
  aarch64-covered package stops holding it back on that chroot alone.

## Status

Planned
