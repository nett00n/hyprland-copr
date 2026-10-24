# COPR-0027. Zig build system and dependency vendoring

**Tags:** #packaging #tooling

## User Story

As a packager adding a Zig project (e.g. `waylock`), I want `build.system: zig` and an
automatic vendor stage for its `build.zig.zon` dependencies, so that the offline mock
chroot (and COPR) can build it the same way Go and Rust packages are built, without
hand-written `zig build` boilerplate or a hand-made dependency tarball.

## Behavior

`build.system: zig` selects Fedora's `zig-rpm-macros` defaults: `%build` runs
`%zig_build -Dpie`, `%install` runs `%zig_install -Dpie`. `build.commands`/`build.install`
override them like for any other system (e.g. `-Dllvm=true`, see Quirks).

Adding `zig` to `build_requires` opts the package into the vendor stage, exactly like
`golang`/`cargo` do. `stage-vendor` downloads the hash-pinned upstream tarball, runs
`build.vendor_prep` (#COPR-0025), then `zig build --fetch` against a scratch
`--global-cache-dir`, which unpacks every `build.zig.zon` dependency into `zig-pkg/<hash>/`
in the source tree (the Zig 0.16 layout). `zig-pkg/` is packed as
`<name>-<version>-vendor.tar.gz`; `%prep` extracts it at the source root (the existing
`tar xf %{SOURCE<n>}` auto-injection in `stage-spec.py`), and `%zig_build` passes
`--system "zig-pkg"`, which disables all network access and errors on a missing package.
A project with no dependencies yields an empty `zig-pkg/`.

```mermaid
flowchart LR
  D[download + verify tarball] --> P[vendor_prep]
  P --> F["zig build --fetch"]
  F --> T["zig-pkg/ -> vendor tarball"]
  T --> M["mock: tar xf, zig build --system zig-pkg (offline)"]
```

`stage-vendor` fails loud on toolchain skew: `build.zig.zon`'s `minimum_zig_version` is
compared (via `dnf repoquery zig`) with what the target Fedora release installs into the
chroot. The vendor store key includes `zig version` of the container toolchain, like
`go version`/`cargo --version` (#BUG-0111).

## Implementation

- `scripts/lib/build_systems.py` — `zig` entry.
- `scripts/lib/vendor.py` — `is_zig_package()`, `needs_vendoring()`, dispatch in `generate()`.
- `scripts/lib/vendor_zig.py` — `generate()` backend (fetch + pack `zig-pkg/`).
- `scripts/lib/toolchain.py` — `parse_zig_minimum_version()`, `zig_toolchain_skew()`.
- `scripts/lib/vendor_store.py` — `zig version` in the key, language `zig`.
- `scripts/lib/validation.py`, `scripts/lib/detection.py` — `zig` is a valid system,
  detected from `build.zig` (before the generic `make` marker).
- `scripts/scaffold-package.py` — zig `build_requires`, vendor archive, `%{_bindir}` file.
- `Containerfile` — `zig` installed for vendoring.

## Quirks & Decisions

- Quirk: Zig is only compatible with its own minor release, so a package tracks whatever
  `zig` Fedora ships; the skew check catches an upstream that moves ahead of a chroot.
- Quirk: Zig's self-hosted backend writes no build-id note, and `find-debuginfo` then
  fails the build (`No build ID note found`). A package whose build exposes an LLVM switch
  (waylock: `-Dllvm=true`) sets it through `build.commands`/`build.install`; otherwise
  set `rpm.no_debug_package: true`.
- Quirk: on Copr's aarch64 builders `zig build` with the default `-Dtarget=native` fails to
  link `waylock` (`ld.lld: undefined reference: stat64@GLIBC_2.33` from `libxkbcommon.so`,
  build 11198729; zig detects its target as `gnu.2.31` there). x86_64 is fine and the
  failure does not reproduce under qemu-user mock. Pinning an explicit `-Dtarget=...-gnu.X`
  does NOT work (zig then stops searching system libraries). `waylock` therefore passes
  `--libc zig-libc.txt` (a libc paths file written in `build.commands`) so zig links the
  chroot's real glibc instead of its own stubs (so `glibc-devel` is a `build_requires`:
  the minimal mock buildroot has no libc headers). Experimental: if the aarch64 chroots still
  fail, restrict the package to x86_64 instead.
- Decision: no `zig_subdir` field until a package needs one; `vendor_prep` can already
  reshape the tree.
- Decision: the vendor tarball holds `zig-pkg/` only, not a global cache, because
  `--system` is the documented offline-packaging path upstream.

## Testing

### Unit

- `tests/test_vendor_zig.py` — missing/failing `zig`, no `build.zig.zon`, fetch failure,
  fetch arguments, tarball holds `zig-pkg/`, empty tree for no deps, skew blocks fetch.
- `tests/test_waylock_zig_libc.py` — the generated `waylock` spec writes `zig-libc.txt`
  in `%build` and passes `--libc zig-libc.txt` to both `%zig_build` and `%zig_install`.
- `tests/test_vendor.py` — `is_zig_package`, `needs_vendoring`, dispatch, ambiguity.
- `tests/test_toolchain.py`, `tests/test_vendor_store.py`, `tests/test_detection.py`,
  `tests/test_validation_gaps.py`, `tests/test_scaffold_package.py`,
  `tests/test_stage_spec.py` — each zig addition above.

### Manual

- `make full-cycle PACKAGE=waylock`, then install the RPM in a clean Fedora container and
  run `waylock -version` / `-h`.

## Status

Implemented
