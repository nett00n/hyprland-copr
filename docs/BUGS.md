# Bugs & debt

Automation behaving wrong today, tech debt, and chores on already-shipped behavior.
New-feature ideas go in `docs/TODO.md` instead (promoted to a `docs/features/` doc
once substantial). GitHub issues are for reporter-facing items (someone else's
bug/request); this file is the maintainer's own log and may cite issue numbers.
Entries are deleted when fixed (the fix gets a `docs/CHANGELOG.md` bullet); IDs are
never reused or renumbered, so deletions leave gaps. Next free ID: **BUG-0106**.

This file absorbed `docs/TODO.md`'s former defect/debt/chore entries on 2026-09-15
when `docs/` adopted `docs/DOCS-DRIVEN-DEVELOPMENT.md` — see `docs/ID-MIGRATION.md`
for the old-ID → new-ID map (BUG-0057 through BUG-0102) and which entries were
promoted to `docs/features/` instead of migrated here.

Each entry ends with a `[P#/D#]` marker:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

Exactly three `##` sections below are mandatory (per
`docs/DOCS-DRIVEN-DEVELOPMENT.md`); `###` topic subheadings inside them are just
navigation, added once a section grows past a handful.

## Unsorted

Not investigated enough to file properly: no verified root cause, no priority, no
difficulty. Move an entry into a real section below once it has all three.

(empty as of the 2026-08-18 grooming pass)

## Bugs & quirks

Shipped behavior doing the wrong thing.

### Copr / cache

- #BUG-0018 local mock used to only ever build one `FEDORA_VERSION`/chroot, but a
  `COPR_REPO` project builds every chroot configured on Copr (fedora-43/44/rawhide
  x86_64/aarch64, 6 total for `nett00n/hyprland`) -> a build that passes local mock
  could still fail on Copr for a chroot-specific reason (the recorded case:
  `Hyprland-git` 0.56.0^20260730git8668a53, local mock built fedora-44 clean, Copr's
  fedora-43-x86_64/aarch64 failed on `std::ranges::starts_with` needing a newer
  libstdc++ than F43 ships). `make full-cycle-matrix` now runs the local pipeline
  across every `MATRIX_VERSIONS` (default: `SUPPORTED`) x86_64 chroot before a single
  Copr submission, and `stage-copr`/`full-cycle` print a per-chroot local-mock
  coverage table before submitting (warn by default, `REQUIRE_CHROOT_COVERAGE=true`
  blocks) -- see `lib.copr.print_chroot_coverage`/`chroot_coverage`/
  `get_project_chroots`. What remains: aarch64 chroots have no local build path at all
  (mock can't cross-build without qemu-user-static or a native runner, see
  [COPR-0020](features/COPR-0020-aarch64-local-builds.md)), so they always report "not
  verifiable locally" and can never satisfy the coverage gate -- that residual is the
  only way this bug can still bite. `lib.copr.fetch_failed_chroot_logs` still
  downloads failed chroots' builder logs after the fact for `make stage-log-analyze`,
  which remains the only diagnostic for an aarch64-only failure [P2/D4]
### Docs / templates

- #BUG-0030 `templates/_contributors.j2`'s `{% if c.github_user %}...{% endif %}` is a
  block tag, and the shared Jinja env (`lib/jinja_utils.py:13-19`) sets
  `trim_blocks=True` -> the newline right after `{% endif %}` is eaten on every loop
  iteration, so contributor entries render concatenated on one line with no `-`
  before the second name. `collect_contributors()` (now in
  `lib/readme_content.py:12-27`, moved out of `gen-report.py` in the 2026-08-03
  refactor -- shared by `gen-report.py` and `gen-readme-shell.py`) reads the commit
  email but dedupes by name only, so the same person committing under two
  `user.name` values also renders as two separate entries. Both defects are visible
  together today in the committed `docs/full-report.md:1072`. `README.md`/
  `docs/README.copr.md` look clean only because `publish-readme.yml`'s
  `actions/checkout@v4` uses the default shallow `fetch-depth: 1` (`:21`), so CI's
  `git log` only ever sees one author -- a local `make readme` on a full clone
  reintroduces both defects there too. `repo.yaml`'s `documents.sections.contributors:
  false` (CHANGELOG 2026-08-xx) is an existing workaround, not a fix. Needs both: a
  `{%- endif -%}` (or restructure without the inline if) in the template, and
  `collect_contributors()` deduping by email instead of name [P3/D1]

- #BUG-0031 nothing verifies that the generated docs body (packages table + build
  status in `README.md`, `docs/README.copr.md`, `docs/full-report.md`) still matches
  `packages.yaml`/`build-report.db`. The README *shell* is CI-regenerated on every
  push to main via `publish-readme.yml` + `gen-readme-shell.py`, but the body needs
  `make readme`, which needs `build-report.db` -- gitignored, so CI has no build
  history to render from. Live drift as of 2026-08-18: README's build-status line says
  `Fedora 44 · 2026-08-09`, `packages.yaml` now has 49 packages, `docs/full-report.md`
  still renders 45 rows. A CI step running `make readme && git diff --exit-code` would
  catch it but needs a design decision first (commit a report snapshot? skip the
  COPR-status-dependent parts of the diff check?) [P2/D3]

### update-daily

`make update-daily` (Makefile) chains update-versions -> validate-packages+fmt ->
refresh-checksums -> full-cycle-matrix -> validate-packages -> readme+copr-description ->
stage-log-analyze -> git commit -> optional push, and is documented
(docs/operations.md) as the unattended nightly job. Audited end to end 2026-08,
re-verified 2026-08-18, revalidation step added 2026-08-29 (BUG-0044). `full-cycle`
was replaced by `full-cycle-matrix` in ce1d02de (2026-09-08, "run full matrix build
before pushing to copr"), found while investigating why three consecutive
2026-09-07/08 runs (commits d303dced, f7363082) pushed nothing to Copr despite
`update-daily` reporting success and committing normally. All three causes found in
that investigation are now fixed -- BUG-0053 (`make -k` plus an order-only
prerequisite silently skipped every non-canonical chroot whenever the canonical one
had any package failure), BUG-0050 (`stage-copr`'s exit code being discarded), and
BUG-0051 (a chroot with zero locally-verified packages silently held back the whole
submission and still exited 0) -- see docs/CHANGELOG.md's 2026-09-08 section:

- #BUG-0039 any package resubmitted tonight is published as `unknown`; only unchanged
  (cached) packages keep showing yesterday's resolved state (as of 2026-08-18,
  `docs/full-report.md` shows 45 `copr-success` rows and 1 `copr-unknown`, not "every
  build"). `full-cycle` submits with `--nowait` (async is the default; `update-daily`
  never sets `SYNCHRONOUS_COPR_BUILD`, though it is read at `stage-copr.py:184` and
  `full-cycle.py:153`), and `readme`+`copr-description` run seconds later -- the
  publish step is simply one poll too early for whatever was just resubmitted [P2/D3]
### Packaging metadata

- #BUG-0047 `lib/rpm_macros.py:normalize_file_entry`'s forward direction (abs -> macro)
  only matches entries starting with `/` (`rpm_macros.py:59`), so a `files:` entry already
  in non-canonical `%{_prefix}/...` form (e.g. `%{_prefix}/bin/ags`, verified live at
  `packages.yaml:75-76`, 39 such entries total across the file) is never canonicalized to
  `%{_bindir}`/`%{_libdir}`/etc, even though `make normalize-paths --reverse` followed by
  a forward pass *does* canonicalize them (round-trip is not idempotent forward-only).
  Also: `PREFIXES` (`rpm_macros.py:6-25`) has no `/usr/lib` entry, so `/usr/lib/x` (as
  opposed to `/usr/lib64/x`) falls through to `%{_prefix}/lib/x` on the reverse pass
  too. Cosmetic only -- both forms are valid RPM spec syntax -- but inconsistent with the
  rest of the file [P3/D2]

- #BUG-0092 vendor stage's `log` field is missing from 5 skip paths, not just the
  "tarball already exists" one: `stage-vendor.py:72` (config skip), `:92`
  (not-vendored), `:104` (spec failed), `:132` (tarball exists), `:144` (vendor-store
  hit) -> inconsistent stage rows. Decide first whether a `log` pointing at an empty
  file is better than `NULL` for the report renderer [P2/D1]

- #BUG-0105 `hyprland-protocols` 0.7.1 shipped upstream's `meson -> cmake` switch
  (commit `3f3860b`, `meson.build` deleted, `CMakeLists.txt` added) but
  `packages.yaml` still declared `build.system: meson`, so `%meson`/`%meson_build`
  ran against a tree with no `meson.build` -> `mock` failed with "Neither source
  directory nor build directory contain a build file meson.build" on all three
  chroots (runs 136-138), and cascaded to 5 dependents
  (`Hyprland`/`hypridle`/`hyprsunset`/`xdg-desktop-portal-hyprland`/
  `hyprland-plugins`) via their skipped `mock` stage. Nothing flagged the drift
  before mock did -- `detect_build_system()` (`lib/detection.py:63`) only ever runs
  at `scaffold-package.py` package-creation time, never again after. Fixed the
  package (`build.system: cmake`, `build_requires: [cmake, ninja-build]`) and added
  `lib.validation.validate_build_system_drift` (`make validate-packages`, warning
  only, offline via `git ls-tree` on the tagged/pinned commit -- see
  [COPR-0010](features/COPR-0010-quality-gate.md)) to catch this class going
  forward. What remains: it's warning-level so a silent false positive (a repo
  shipping both marker files mid-migration) can't block `make update-daily`;
  promoting it to an error is worth revisiting once it's run quiet for a while
  [P3/D1]

### Makefile

- #BUG-0071 `delete-package.py:95-97` now cleans the artifacts ledger
  (`build_db.forget_package`, `lib/build_db.py:431-436`) but never touches
  `local-repo/*/<pkg>-*.rpm` -> stale RPMs linger across every target, and are now
  *worse off* than before: they survive on disk with no DB row pointing at them
  anymore. Fix needs a glob-and-unlink plus `regenerate_repo_metadata` per touched
  target, or dnf metadata goes stale [P2/D2]

## Tech debt

Refactor / typing / dedup / structure with no behavior change.

### Build matrix (arch / non-fedora distros)

Db key is already `target` (= mock chroot, e.g. fedora-44-x86_64) and `runs` carries
distro/distro_version/arch, so aarch64 and centos need no schema change. The
distro/arch-agnostic build-target work itself is tracked as a feature, not here — see
[COPR-0019](features/COPR-0019-build-target.md) (Planned).

### Makefile

- #BUG-0066 two different multi-package loop strategies coexist: Makefile-side
  `_PKGS` loop (`Makefile:123`, used by `sources` and `stage-log-analyze`) vs
  pass-PACKAGE-to-python (every `stage-*` target) -> pick one [P3/D1]
- #BUG-0067 `full-cycle-matrix`'s `matrix-chroot-%` targets (`Makefile`) build every
  chroot in `MATRIX_VERSIONS` serially via a plain shell `for` loop in
  `_full-cycle-matrix` (was `$(MAKE) -k` plus an order-only prerequisite until
  BUG-0053's fix), even though the chroots are
  independent once the canonical one has run. `-j` isn't supported: the canonical
  chroot's release-bump step (`SKIP_RELEASE_BUMP`, BUG-0049) writes the shared
  `packages.yaml` while every other chroot's `full-cycle` call reads it, and the
  pipeline `flock` (BUG-0043) refuses a second concurrent `make` invocation by
  design anyway -- both would need solving first [P3/D3]
- #BUG-0069 `ALL_PACKAGES` (`Makefile:118`) parses packages.yaml with a grep regex
  instead of the yaml lib used everywhere else -> fragile, switch to yaml. Caveat:
  it's a `$(shell)` evaluated at parse time on *every* make invocation, so a naive
  swap to python adds interpreter startup to every target -- needs a cache, not a
  straight swap [P2/D1]
- #BUG-0070 `add-submodule`/`add-new` still embed real logic (yaml edits, git
  submodule surgery) directly in Makefile recipes (`Makefile:330-349`) instead of
  scripts/*.py -> untestable by pytest. `delete-package` still holds submodule surgery
  and the volume sweep in the recipe after its script call (`Makefile:356-376`).
  `scaffold-package` is already done -- it fully delegates to
  `scripts/scaffold-package.py`, which is tested [P2/D3]

### Scripts

- #BUG-0076 `scripts/full-cycle.py:run_build_pipeline` is 425 lines
  (`full-cycle.py:267-691`, grown from ~320) of repeated per-stage orchestration
  (spec/vendor/srpm/mock/copr all same shape: cache check -> run_for_package ->
  build_db.finalize_stage) -> candidate for a small stage-runner abstraction. Do
  together with BUG-0077 -- same file family, same shape [P3/D4]
- #BUG-0077 each `stage-*.py` (validate/spec/vendor/srpm/mock/copr) copy-pastes its
  own "config: skip" `set_stage()` call (~6 lines x6, e.g. `stage-srpm.py:76-81`,
  `stage-vendor.py:70-75`) -> extract to a small helper (the old `lib/stage_utils.py`
  was removed in the sqlite migration; a new home is needed, e.g.
  `lib/stage_common.py`) [P3/D1]
- #BUG-0083 `lib/log_analysis.py` is 1257 lines (re-verified 2026-08-18, grown from
  944) of ~41 copy-pasted `if m: issues.append(...); continue` blocks from
  hand-written regexes -> a data table of (regex, formatter) pairs would cut it by
  half+. Well covered by `tests/test_log_analysis.py` +
  `tests/test_log_analysis_gaps.py`, making this an unusually safe refactor [P3/D4]
- #BUG-0084 `vendor_golang.py`/`vendor_rust.py` hand-roll subprocess+log-writing
  instead of using `lib/subprocess_utils.run_cmd`, which already does exactly that.
  Both files are tested, so this is safe; watch `vendor_rust.py:62`'s probe call,
  whose semantics may not map cleanly onto `run_cmd`'s return shape [P2/D2]
- #BUG-0087 `scripts/pkg-log-analysis.py:6-15` imports eight underscore-prefixed
  "private" functions directly from `lib.log_analysis`, and redefines
  `HIGHLIGHT_PREFIX` locally (`:18`) as a third copy of that constant -> either make
  the functions public API or move this script's logic into lib/. Best done together
  with BUG-0083, since that refactor changes these function boundaries anyway [P3/D2]
- #BUG-0091 `_download()` in `lib/vendor.py:77-80` reads the whole archive into
  memory (`dest.write_bytes(resp.read())`) instead of streaming to disk with
  `shutil.copyfileobj`. `verify_download()` runs right after
  (`lib/vendor.py:87,168`), so streaming doesn't weaken the checksum guarantee [P2/D1]
- #BUG-0093 every record in the codebase is an unparameterized `dict` -- 134 bare
  `dict`/`list`/`tuple` annotations, and exactly one structured type in all 12k
  lines (`update-versions.py:42`'s `Pin`, a `NamedTuple`). Unlocks mypy's
  `disallow_any_generics` (155 errors on the current tree; left off in `mypy.ini`
  pending this). Three shapes worth naming, in payoff order: (1) the stage-results
  row -- built by `_stage_entry` (`lib/build_db.py:148-158`), consumed via `.get()`
  in `lib/pipeline.py`, `lib/copr.py:341-345`, `gen-report.py:95-102`,
  `lib/version.py:152`. `_row_dict` (`build_db.py:139`) deliberately *drops NULL
  columns* so absent-key defaults keep working -- a contract stated in a docstring
  and enforced nowhere; a `TypedDict(total=False)` states it in the type system.
  (2) package metadata from `packages.yaml`. (3) `compute_input_hashes()`'s
  `-> dict` (`lib/cache.py:102-117`), whose five keys are compared by whole-dict
  equality in `hashes_match()` (`:120-123`). Do the stage row first -- it's the one
  with the documented-but-unchecked invariant [P2/D4]
- #BUG-0094 stage and state names are magic strings across 16 files.
  `build_db.STAGES` (`lib/build_db.py:18`) and `copr.TERMINAL_STATES`
  (`lib/copr.py:31`) exist but are values, not types: every `stage`/`state`
  parameter is plain `str` and the literals are retyped by hand ~190 times --
  `full-cycle.py` (28), `lib/reporting.py` (24), `lib/copr.py` (18),
  `stage-copr.py` (17), `lib/pipeline.py` (16), and 11 more files. A typo is a
  silent mismatch, not an error: the same shape as BUG-0014 (an unrecognized
  `release_type` falling through a dispatch) and BUG-0002 (`unknown` vs
  `success`). Fix: `Stage`/`State` `Literal` aliases in `lib/build_db.py`, applied
  to `set_stage`/`finalize_stage`/`get_stage` first. `lib/version.py:20-48`
  already does the value half of this well (`RELEASE_TYPES` and friends as
  `frozenset`s with a "single source of truth" comment); this is the type half of
  the same idea [P2/D2]
- #BUG-0095 `Any` laundered through annotated signatures -- a function annotated
  `-> str | None` / `-> dict` / `-> bool` returning a raw `yaml.safe_load` /
  `json.loads` / `.get()` result. Unlocks mypy's `warn_return_any` (17 errors on
  the current tree; left off in `mypy.ini` pending this). Worst are the trust
  boundaries: `lib/yaml_utils.py:33`, `lib/github.py:54,121`. The annotation is
  the fake here -- the caller sees `str`, the value is `Any`. Fix: typed loader
  wrappers that validate at the parse boundary, after which the annotations
  become true. `gen-spec.py:410`'s `url_to_submodule: dict[str, object]` is the
  same tell in the other direction -- values are `Path`, declared `object`, and
  the parameter receiving it (`gen-spec.py:214`) is a bare `dict` [P2/D3]

### Daily update

Design/complexity items found while auditing `make update-daily` end to end
(2026-08). Automation actually misbehaving from these findings is filed under
`## Bugs & quirks` "update-daily" above instead.

- #BUG-0101 add concurrency (e.g. `ThreadPoolExecutor`) to `update-versions.py`'s
  per-submodule pull/fetch loop -- split out from BUG-0100 because it's a different
  risk profile (shared `.git/modules` state) from the reporting fix [P3/D3]

## Chores

Mechanical maintenance: pinning, renames, dead-code removal, small tooling additions.

### Makefile

- #BUG-0068 `HIGHLIGHT_PREFIX` default (`Makefile:13`) bakes literal quote chars into
  the value as a hack so unquoted `echo $(HIGHLIGHT_PREFIX) "text"` works;
  check-image/check-venv/setup-volumes instead embed it inside a quoted string ->
  fragile, one edit away from breaking output. Touches ~80+ echo sites across the
  Makefile -- simplify to plain value + consistent quoting everywhere [P3/D1]

### Scripts

- #BUG-0074 `scripts/gen-spec.py` (446 lines) duplicates `lib/github.py`
  (`_cache_key`/`load_release_cache`/`save_release_cache`/`fetch_github_release`/
  `build_changelog`) and `lib/config.get_packager` almost verbatim, has no Makefile
  target, unused except by its own test -> looks like a dead pre-pipeline prototype,
  remove or replace with lib calls. Check first whether `build_context()`
  (`gen-spec.py:210-380`) has spec-rendering logic `stage-spec.py` lacks before
  deleting [P3/D4]
- #BUG-0075 `tests/conftest.py` and `tests/integration/conftest.py` are ~93%
  identical (36-line diff across 96/102-line files) -- real differences are just a
  docstring, a path-depth difference, and one extra `monkeypatch_cwd` fixture -> dedupe
  down to that one fixture [P3/D1]
- #BUG-0085 3 YAML modules mix PyYAML-load and ruamel-dump inconsistently with no doc
  on which to use when: `lib/yaml_config.py` is ruamel-only, `lib/yaml_utils.py` is
  PyYAML-only, `lib/yaml_format.py` mixes both (docstring advertises ruamel but
  `:44`/`:150` call `yaml.safe_load`) -> confusing for newcomers. A docstring in each
  module solves the stated pain more cheaply than consolidating [P3/D1]
- #BUG-0088 `Containerfile:9-21` installs cargo/golang/mock/rpmlint with no version
  pins, and the base image tag (`Containerfile:3`) floats too -> minor reproducibility
  risk over time. Pinning individual packages against a floating Fedora base just
  creates dnf resolution failures the moment the base updates; the honest fix is
  digest-pinning the base image itself [P3/D2]
- #BUG-0090 `_log_fn` in `lib/vendor.py` is underscore-private but imported directly
  by `vendor_golang.py:9`/`vendor_rust.py:14` (`_download`/`_extract` no longer have
  external importers as of 2026-08-18, so this is now `_log_fn` only). Naturally
  resolved by BUG-0084 -- moving those modules to `run_cmd` removes the need for it
  [P3/D1]
### Docs

- #BUG-0103 `docs/DOCS-DRIVEN-DEVELOPMENT.md`'s Rules require every top-level
  function/class implementing a feature to carry the `#COPR-NNNN` IDs it implements,
  as a comment directly above it or the first docstring line. Not yet applied
  anywhere in `scripts/`/`scripts/lib/` -- deliberately out of scope for the DDD
  adoption change itself (essentially every top-level function in the codebase),
  filed here so it isn't forgotten [P3/D4]
