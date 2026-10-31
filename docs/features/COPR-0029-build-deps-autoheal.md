# COPR-0029. Build-dependency autoheal

**Tags:** #build #mock #automation #diagnostics

## User Story

As a maintainer, I want a mock build that fails on a missing build dependency to fix
itself — add the dependency to `packages.yaml` and rebuild — so that an upstream release
which adds one more `pkgconfig(...)` or CMake dependency does not fail every chroot,
every night, until I notice and edit `build_requires` by hand.

## Behavior

When the mock build of a package fails, `stage-mock` scans that build's
`21-mock-build.log` ([COPR-0009](COPR-0009-log-analysis.md) analyzers) for a missing
dependency, resolves it to a `packages.yaml` entry, edits `packages.yaml`, regenerates the
spec and SRPM and runs mock again. This applies to every way of building, because they all
go through `stage-mock`: `make stage-mock`, `make full-cycle`, `make full-cycle-matrix`
and `make update-daily`.

**Triggers** (the only failures that are healed):

- CMake `pkg_check_modules` "The following required packages were not found" — every
  package listed, with any version constraint stripped (`hyprtoolkit>=0.6.0` →
  `hyprtoolkit`).
- meson `Dependency "X" not found, tried pkgconfig`.
- CMake "Could not find a package configuration file provided by X" and "By not
  providing FindX.cmake" (CMake config packages).

Everything else (missing binaries, libraries, macros, vendoring, source errors) is left
failed as before.

**Resolution** of each missing dependency, in order:

1. **Local package.** The name matches a `packages.yaml` package (case-insensitive) that
   has a `devel` subpackage and is not the package being built: add `<pkg>-devel` to
   `build_requires`, and `<pkg>` to `depends_on` when the package already has one. An
   absent `depends_on` means "infer from `-devel` names" (`lib/deps.py`), so it is never
   created: a new list holding only the new entry would drop every inferred dependency.
2. **Fedora package.** `dnf repoquery --whatprovides 'pkgconfig(X)'` (or `cmake(X)`)
   against the target's Fedora release finds a provider: add `pkgconfig(X)` (or
   `cmake(X)`) to `build_requires`.
3. **No provider** found: nothing is changed and the build stays failed. A dependency is
   never guessed.

**Loop and limit.** A heal cycle is: resolve → edit `packages.yaml` → spec → SRPM → mock.
At most `AUTOHEAL_MAX_CYCLES` cycles run per package per invocation (default `10`). The
loop ends early on success, or when a cycle can add nothing new (no recognised dependency,
no provider, or every entry already present). If the build still fails after the last
cycle, the mock stage is **failed** with `reason` `autoheal: gave up after N cycles (+…)`.
Entries already added stay in `packages.yaml`: each was a provider-verified missing
dependency.

**Switches.** On by default. `AUTOHEAL=false` (also `0`/`no`) restores the old behavior:
the mock stage fails and nothing is edited. `AUTOHEAL_MAX_CYCLES=<n>` overrides the limit.
Both are passed through into the container.

**Reporting.** Each rebuild emits a `mock ... autoheal` event line and an INFO log line
naming the entries added. The mock stage `reason` lists them, e.g. `autoheal:
+pkgconfig(libcanberra), +hyprtoolkit-devel (2 cycles)`, or `autoheal: gave up after 10
cycles (+…)` on failure. [COPR-0028](COPR-0028-last-build-stats.md)'s `make last-build`
lists these rows in an "Autohealed" section. The daily update commits the edited
`packages.yaml` like any other change.

## Implementation

- `scripts/lib/log_analysis.py`: the CMake `pkg_check_modules` branch emits one issue per
  package with the version constraint stripped (`_strip_constraint`); CMake
  config-package issues carry method `cmake`; `_suggest_providers` handles `cmake`;
  `_dnf_whatprovides` takes `extra_args` and ends `--qf` in an explicit `\n`.
- `scripts/lib/deps_autoheal.py`: `autoheal_enabled()`, `max_cycles()`,
  `missing_build_deps()`, `resolve_dep()`, `apply_fixes()` (reads with PyYAML, writes
  with `write_yaml_file` like `update_package_releases()`; appends then sorts
  `build_requires`; never removes) and `heal_loop()`.
- `scripts/stage-mock.py`: `_mock_cmd()` and `_run_mock_once()` (the former inline mock
  invocation), `_rebuild_healed()` (reload `packages.yaml`, rerun `stage-spec` and
  `stage-srpm`, rerun mock) and the `heal_loop` call in `run_for_package`.
- `scripts/full-cycle.py`: `rehash_after_autoheal()` reloads the package and re-stamps
  the spec/vendor/srpm hashes so the edited entry is a cache hit next run, and the
  mock row keeps the `autoheal:` reason.
- `scripts/last-build.py`: the "Autohealed" section.
- `Makefile`, `.env.example`: `AUTOHEAL` and `AUTOHEAL_MAX_CYCLES`, passed into the
  container only when set (unset means the defaults: on, 10).

## Quirks & Decisions

- The existing `preflight_autoheal()` in `full-cycle.py` (missing mirrors and checksums)
  is a separate, earlier mechanism; both share the "autoheal" name, not code.
- Only additions: the heal never removes or rewrites an entry, so a wrong addition is
  visible in `git diff` and trivially reverted.
- A cycle that re-adds an entry already present counts as "nothing new": a dependency
  the spec already lists but mock still cannot find is not something an edit can fix.
- `packages.yaml` is edited in place mid-run. `update_package_releases()` rewrites it at
  the end of `full-cycle`, so the heal re-reads the file for each edit instead of holding
  a stale copy.
- Resolution uses the target's own Fedora release (`dnf --releasever`), not the
  container's, so an F45-only dependency is not "verified" against F43.
- Rewriting `packages.yaml` goes through the same PyYAML-load / ruamel-dump path as the
  other automated writers, so YAML comments are not preserved (as for release bumps).
- No automatic removal when upstream drops a dependency; that stays with
  `validate_dependency_drift` warnings ([COPR-0010](COPR-0010-quality-gate.md)).

## Testing

`tests/test_log_analysis.py`: one issue per package with stripped constraints; `cmake`
method for config-package errors; `cmake(X)` provider lookup; the `--qf` newline.
`tests/test_deps_autoheal.py`: log → missing deps (HTML-escaped constraints too); Fedora
provider → `pkgconfig(X)`/`cmake(X)`; local package → `<pkg>-devel` + `depends_on`; no
provider → no fix; sorted insert without duplicates; `depends_on` never created;
the switches; `heal_loop` with one cycle, two cycles, the cycle limit (failed, "gave up"),
and early stops. `tests/test_stage_mock_autoheal.py`: the stage row after a healed or
exhausted loop, `AUTOHEAL=false`, `AUTOHEAL_MAX_CYCLES`, `_rebuild_healed` ordering, and
`rehash_after_autoheal`. `tests/test_last_build.py`: the "Autohealed" section.

## Status

Shipped.
