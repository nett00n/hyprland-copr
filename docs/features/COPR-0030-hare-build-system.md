# COPR-0030. Hare build system

**Tags:** #packaging #tooling

## User Story

As a packager adding a Hare project (e.g. `wlhc`), I want `build.system: hare` with
sensible defaults and the Hare toolchain available as ordinary packages in this repo, so
that a Hare program builds in the offline mock chroot (and COPR) like any other package,
without hand-written `hare build` boilerplate.

## Behavior

`build.system: hare` selects these defaults: `%build` runs
`hare build -R -o %{name} .`, `%install` runs
`install -Dm755 %{name} %{buildroot}%{_bindir}/%{name}`. `build.commands`/`build.install`
override them like for any other system (e.g. `wlhc`, whose upstream `Makefile` must
first generate the Wayland protocol bindings with `hare-wlscanner`).

There is no vendor stage. Hare dependencies are source libraries installed by RPM under
`%{_prefix}/src/hare/third-party` (on the default `HAREPATH`), so they are plain
`build_requires` on the library packages (`hare-ev`, `hare-wayland`), built from this
repo like any other `depends_on` chain.

The toolchain itself is packaged here as ordinary `make` packages: `harec`, `hare`,
`hare-ev`, `hare-xml` and `hare-wayland` (whose `hare-wlscanner` needs `hare-xml`).
Fedora ships `harec` (0.25.2 on F43/F44, 0.26.0 on F45) but
no `hare` driver/stdlib, `hare-ev` or `hare-wayland`. The stdlib must match the `harec`
minor release, so this repo ships `harec` too and tracks upstream `0.26` on every chroot.

`scaffold-package` detects Hare from a top-level `main.ha` (before the generic
`Makefile` marker).

## Implementation

- `scripts/lib/build_systems.py` — `hare` entry.
- `scripts/lib/validation.py` — `hare` is a valid `build.system`.
- `scripts/lib/detection.py` — `main.ha` marker, ahead of `make`.
- `scripts/scaffold-package.py` — hare `build_requires` and `%{_bindir}` file.

## Quirks & Decisions

- Quirk: the Hare stdlib must match `harec` exactly, so `harec` and `hare` are bumped
  together; ours replaces Fedora's `harec` on F43/F44.
- Quirk: tags have no `v` prefix and may have four parts (`0.26.0.1`); `lib.version`
  already handles both, so `auto_update.release_type: latest-tag` works.
- Quirk: `hare-wayland` tracks `latest-commit`, not its tag: tag `0.26.0.2` predates the
  parser support for the `deprecated-since` attribute that Fedora's `wayland.xml` uses
  (`hare-wlscanner` fails with `XML does not fulfill required schema`).
- Quirk: Hare's `scripts/version` falls back to a hardcoded version without `.git`, so
  `harec`/`hare` pass `VERSION=%{version}` to `make`.
- Quirk: Hare-built binaries carry no build-id, so `find-debuginfo` fails; Hare-built
  packages (`hare`, `hare-wayland`, `wlhc`) set `rpm.no_debug_package: true`. `harec` is C
  and keeps debuginfo.
- Quirk: upstreams live on sourcehut, whose archive URL is `%{url}/archive/<tag>.tar.gz`,
  not GitHub's `archive/refs/tags/...`. The scaffolder writes the GitHub form, so the
  `source.archives` entry is fixed by hand (see `docs/TODO.md`).
- Quirk: Hare targets x86_64, aarch64 and riscv64 only.
- Decision: no toolchain-skew check like Zig's, because `harec` and `hare` ship together.

## Testing

### Unit

- `tests/test_detection.py` — `main.ha` detects `hare`; it wins over a generic `Makefile`.
- `tests/test_validation_gaps.py` — `hare` is valid; defaults render as above.
- `tests/test_scaffold_package.py` — a hare scaffold gets `hare` in `build_requires` and
  `%{_bindir}/<name>` in `files`.

### Manual

- `make full-cycle PACKAGE=wlhc` (after `harec`, `hare`, `hare-ev`, `hare-wayland`), then
  install the RPM in a clean Fedora container and run `wlhc -h`.

## Status

Implemented
