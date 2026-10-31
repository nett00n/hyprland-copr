# COPR-0029. Build autoheal: dependencies and file lists

**Tags:** #build #mock #automation #diagnostics

## User Story

As a maintainer, I want a mock build that fails on a missing build dependency to fix
itself — add the dependency to `packages.yaml` and rebuild — so that an upstream release
which adds one more `pkgconfig(...)` or CMake dependency does not fail every chroot,
every night, until I notice and edit `build_requires` by hand. Likewise, when upstream
stops installing a file `files:` still lists (or starts installing one it does not), the
build should be repaired without a hand edit of the file lists.

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
failed as before. The two file-list cases below are healed as well.

**Resolution** of each missing dependency, in order:

1. **Local package.** The name matches a `packages.yaml` package (case-insensitive) that
   has a `devel` subpackage and is not the package being built: add `<pkg>-devel` to
   `build_requires`, and `<pkg>` to `depends_on` when the package already has one. An
   absent `depends_on` means "infer from `-devel` names" (`lib/deps.py`), so it is never
   created: a new list holding only the new entry would drop every inferred dependency.
2. **Fedora package.** `dnf repoquery --whatprovides 'pkgconfig(X)'` (or `cmake(X)`)
   against the target's Fedora release finds a provider: add `pkgconfig(X)` (or
   `cmake(X)`) to `build_requires`. When the log names a version constraint
   (`sdbus-c++>=2.0.0`) it is kept — `pkgconfig(sdbus-c++) >= 2.0.0` — and the provider
   lookup uses the constrained capability, so a release whose newest provider is too old
   counts as "no provider" and the failure stays visible instead of looping. An existing
   bare `pkgconfig(X)` entry is upgraded in place to the constrained one. `cmake(X)`
   entries never carry a constraint.
3. **No provider** found: nothing is changed and the build stays failed. A dependency is
   never guessed.

**File lists** (`files:` and `devel.files:` — the only two lists the spec has). rpmbuild
checks `%files` after `%install`, stops at the first subpackage that fails, and so reports
only one of these two cases per build:

- **Declared but not produced** — `error: File not found: …/BUILDROOT/usr/share/bash-completion/completions/hyprctl`
  (also `File not found by glob`). The declared entry that covers the path (exact match,
  glob, or directory prefix, after expanding its macros) is a *removal candidate*.
  `%doc`/`%license` entries are never touched, an entry with a macro this feature cannot
  expand is never matched, and the last entry of the main `files` list is never removed.
- **Produced but not declared** — `error: Installed (but unpackaged) file(s) found:`.
  Every listed file that no declared entry covers is *added*, as a macro-style entry
  (`/usr/lib64/systemd/user/x.target` → `%{_libdir}/systemd/user/x.target`) to
  `devel.files` when it is under `%{_includedir}`, in a `pkgconfig/` or `cmake/`
  directory or a static `.a` (the repo's `DEVEL_INDICATORS`), otherwise to `files`. Debug
  files are ignored.

**Union rule for removals.** The spec is shared by every chroot, so a file one chroot does
not produce may be produced by another. An addition is always applied (a chroot that does
not produce the file then fails visibly). A removal is applied only when **every
supported chroot agrees**:

1. A chroot that hits the missing file records a *vote* and does not edit or rebuild: its
   mock stage stays **failed** with `reason` `autoheal: pending -files:<entry> (needs all
   chroots; lacking on n/m: <targets>)`.
2. The votes are the latest `mock` rows of every supported target (`mock_chroot(v)` for
   `SUPPORTED_FEDORA_VERSIONS`): a row counts when it is `failed`, has the same upstream
   version, and its reason names the entry. A chroot that later builds fine overwrites its
   row, which withdraws its vote — it produces the file.
3. The chroot whose vote completes the set applies the removal, regenerates spec and SRPM
   and rebuilds like any other heal. The chroots that voted earlier are rebuilt on the next
   run (the package content hash changed).
4. When some chroot produces the file the vote never completes: the lacking chroots stay
   failed with their `pending` reasons for a human, and the heal can never undo itself.

A manual single-chroot run (`make stage-mock FEDORA_VERSION=44`) therefore only records a
vote.

**Loop and limit.** A heal cycle is: resolve dependencies and plan file edits → edit `packages.yaml` → spec →
SRPM → mock.
At most `AUTOHEAL_MAX_CYCLES` cycles run per package per invocation (default `10`). The
loop ends early on success, or when a cycle can change nothing (no recognised dependency,
no provider, every entry already present, only pending removals). If the build still
fails after the last cycle, the mock stage is **failed** with `reason` `autoheal: gave up
after N cycles (+…)`. Edits already made stay in `packages.yaml`: each was a
provider-verified dependency, or a file edit confirmed by the build log (and, for a
removal, by every chroot). A cycle costs a full rebuild — about 31 minutes for Hyprland.

**Switches.** On by default. `AUTOHEAL=false` (also `0`/`no`) restores the old behavior:
the mock stage fails and nothing is edited. `AUTOHEAL_MAX_CYCLES=<n>` overrides the limit.
Both are passed through into the container.

**Reporting.** Each rebuild emits a `mock ... autoheal` event line and an INFO log line
naming the changes. The mock stage `reason` lists them, signed, e.g. `autoheal:
+pkgconfig(libcanberra), +hyprtoolkit-devel, -files:%{_datadir}/… (3 cycles)`, or
`autoheal: gave up after 10 cycles (+…)` on failure, or the `pending` vote above. [COPR-0028](COPR-0028-last-build-stats.md)'s `make last-build`
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
  `build_requires`; never removes) and `heal_loop()`, which each cycle combines the
  dependency fixes with `files_autoheal.plan()` and returns signed `changes`.
- `scripts/lib/files_autoheal.py`: `entry_path()` (entry → absolute path, `None` if a macro
  is unknown), `owners()`, `classify()`, `to_entry()`, `votes()`/`unanimous()`, `plan()` and
  `apply_edits()`.
- `scripts/lib/log_analysis.py` also: the `File not found by glob` matcher, and
  `missing_files()` / `unpackaged_files()` returning plain path lists.
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
- Dependency edits are only additions. File-list edits may remove, but only with the union
  rule above, so a removal cannot be undone by another chroot's addition and the other
  way round; every edit is visible in `git diff` and trivially reverted.
- File-entry macros are expanded locally (`%{_prefix}`, `%{name}`, `%{version}`, the
  bash/fish/zsh completion directories, then `lib/rpm_macros.py`): `lib/rpm_macros.py`
  itself does not know them (BUG-0047) and is left alone.
- A cycle that re-adds an entry already present counts as "nothing new": a dependency
  the spec already lists but mock still cannot find is not something an edit can fix.
- `packages.yaml` is edited in place mid-run. `update_package_releases()` rewrites it at
  the end of `full-cycle`, so the heal re-reads the file for each edit instead of holding
  a stale copy.
- Resolution uses the target's own Fedora release (`dnf --releasever`), not the
  container's, so an F45-only dependency is not "verified" against F43.
- The constraint is read from the log's package list (`- sdbus-c++>=2.0.0`), because the
  issue tuples of [COPR-0009](COPR-0009-log-analysis.md) carry only the stripped name.
- Rewriting `packages.yaml` goes through the same PyYAML-load / ruamel-dump path as the
  other automated writers, so YAML comments are not preserved (as for release bumps).
- No automatic removal of a *dependency* when upstream drops it; that stays with
  `validate_dependency_drift` warnings ([COPR-0010](COPR-0010-quality-gate.md)).

## Testing

`tests/test_log_analysis.py`: one issue per package with stripped constraints; `cmake`
method for config-package errors; `cmake(X)` provider lookup; the `--qf` newline.
`tests/test_deps_autoheal.py`: log → missing deps (HTML-escaped constraints too); Fedora
provider → `pkgconfig(X)`/`cmake(X)`; version constraint kept, checked against the
provider lookup, and upgrading a bare entry; local package → `<pkg>-devel` + `depends_on`; no
provider → no fix; sorted insert without duplicates; `depends_on` never created;
the switches; `heal_loop` with one cycle, two cycles, the cycle limit (failed, "gave up"),
and early stops. `tests/test_stage_mock_autoheal.py`: the stage row after a healed or
exhausted loop, `AUTOHEAL=false`, `AUTOHEAL_MAX_CYCLES`, `_rebuild_healed` ordering, and
`rehash_after_autoheal`, and a pending vote leaving a failed row without a rebuild.
`tests/test_last_build.py`: the "Autohealed" section. `tests/test_files_autoheal.py`:
entry → path (directives, macros, unknown macro), owners by exact/glob/directory, devel
classification, unanimous vs non-unanimous votes (stale version, withdrawn vote), skipping
covered files, sorted/deduped edits, `files: []` kept, the last main entry kept.
`tests/test_log_analysis.py`: the glob matcher and `missing_files`/`unpackaged_files`.

## Status

Shipped.
