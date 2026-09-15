# Bugs & debt

Automation behaving wrong today, tech debt, and chores on already-shipped behavior.
New-feature ideas go in `docs/TODO.md` instead (promoted to a `docs/features/` doc
once substantial). GitHub issues are for reporter-facing items (someone else's
bug/request); this file is the maintainer's own log and may cite issue numbers.
Entries are deleted when fixed (the fix gets a `docs/CHANGELOG.md` bullet); IDs are
never reused or renumbered, so deletions leave gaps. Next free ID: **BUG-0104**.

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
- #BUG-0057 `_templates_hash()` (`lib/cache.py:65-67`) hashes `spec.j2` and
  `hashes_match()` (`lib/cache.py:120-123`) is a strict full-dict equality, so any
  edit to `spec.j2` invalidates all 49 packages' caches at once and force-rebuilds
  everything. Wanted instead: inform that a cached package's spec was generated from
  an outdated template, rather than force a rebuild [P2/D3]
- #BUG-0064 when package B depends on A and `is_cached("mock", B, ...)` returns
  true, nothing verifies A's RPM still exists in `local-repo/<target>/` --
  `is_cached()` (`lib/pipeline.py:100-127`) only checks B's own artifact via
  `artifacts_present()`, and the dependency input is `_dependencies_hashes()`
  (`lib/cache.py:82-90`), which hashes A's packages.yaml *config*, not A's build
  state or on-disk artifact. The actual dependency-file-exists check,
  `check_buildroot_repo()`/`_rpm_present()` (`lib/repo_preflight.py:100-171`), only
  runs inside `stage-mock.run_for_package()` -- which the cached path skips entirely
  (`full-cycle.py:517-519`). Concretely: A and B both build fine; A's RPM later goes
  missing from `local-repo/<target>/` (stale-artifact prune, partial
  `make clean-localrepo`, volume corruption) with A's own `mock` stage row untouched;
  B stays "cached" since B's own hash/artifact are unaffected, so the one check that
  would notice A is gone never runs. The gap only surfaces later, by accident, if
  some other *uncached* package that also depends on A happens to build. Distinct
  from BUG-0017 (wrong-artifact-kept pruning) and BUG-0061 (on-disk corruption
  detection) -- this is about a dependency's *existence*, not its integrity [P2/D3]

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
- #BUG-0099 `full-cycle.py:305-306` unconditionally sleeps 5 seconds after printing
  the build plan "before proceeding" -- an interactive abort window that only burns
  time in the unattended cron flow the target is documented for, and is paid 3x by
  `make full-cycle-matrix` (once per Fedora version). Gate on `sys.stdout.isatty()`
  [P2/D1]
- #BUG-0100 `update-versions.py` (423 lines) fetches 45+ submodules serially on
  every run, and 10 separate warn-and-continue sites
  (`update-versions.py:118,125,137,150,188,327,335,344,361,375`) print individual
  failures to stderr with nothing aggregated -> a single `git fetch` failure is
  invisible in the stdout summary, so a package can silently sit on a stale version
  indefinitely. Scoped down to just the aggregate-failure-report half; see
  BUG-0101 for the concurrency half, split out separately since it's materially
  riskier (git operations on shared `.git/modules`) [P2/D2]

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

- #BUG-0056 a `depends_on` package on `auto_update.release_type: latest-commit`
  (e.g. `hyprland-plugins`) can silently outrun a tag-pinned dependency (`Hyprland`
  at `v0.56.2`): upstream's `722f15a` (2026-09-05) chased Hyprland's unreleased
  `main` API (`window->presentation()/metadata()/backend()`, `WindowPresentation.hpp`,
  `WINDOW_STATE_PINNED`, `S*RenderData`), which doesn't exist in the packaged 0.56.2
  headers, and mock failed on all three chroots (fedora-43/44/45-x86_64, runs 76-78)
  before anyone noticed. Nothing in `make validate-packages`/`stage-validate` flags a
  `latest-commit` package tracking a compositor API ahead of a sibling package's
  pinned version -- the drift is only caught by mock actually failing to compile.
  Fixed for now by pinning `hyprland-plugins` to `00862ca` ("hyprpm: add pin for
  0.56.2", `pinned-commit`) -- the first candidate tried, `faf5ef1`, turned out to
  already carry two more rounds of the same drift (`keybinds/Manager.hpp` replacing
  `managers/KeybindManager.hpp`, `g_layoutManager` drag targets), only surfacing once
  `glslang-devel` was also fixed and the build got further; `00862ca` was verified by
  checking every `hyprland/src/...` header it includes against the `v0.56.2` tag tree
  directly, since upstream's own `hyprpm.toml` pin hash for 0.56.2 has since been
  rewritten and no longer resolves. Unpin back to `latest-commit` once Hyprland 0.57
  is packaged. Also fixed in the same pass, both pre-existing and independent of the
  version pin: `hyprland-devel` was missing `Requires: glslang-devel`/`lua-devel` for
  headers (`ShaderLoader.hpp`, `LuaBindings.hpp`) it ships but doesn't declare
  (fixed via `Hyprland`'s new `devel.requires`, which every future `hyprland-devel`
  consumer now inherits); and `hyprland-plugins`' `files:` glob
  (`%{_prefix}/lib/libhypr*.so`) never matched `libborders-plus-plus.so`/
  `libcsgo-vulkan-fix.so` (non-`libhypr*`-named), so a clean build would have failed
  rpmbuild's unpackaged-files check -- this had never been hit before because no
  `hyprland-plugins` mock build in `build-report.db` had ever reached that far. What
  remains: no automated check for the `latest-commit`-outruns-a-pinned-`depends_on`
  class of drift across any other package pair [P2/D3]
- #BUG-0089 vendoring is triggered by `build_requires` containing `golang`/`cargo`
  (`lib/vendor.py:26-38`, two sources of truth with packages.yaml's Source1 + `tar xf
  %{SOURCE1}`, which must be hand-added and isn't cross-validated) -> silent breakage
  if the pair drifts. No cross-validation exists in `validate-packages.py` or
  `lib/validation.py` today [P2/D2]
- #BUG-0092 vendor stage's `log` field is missing from 5 skip paths, not just the
  "tarball already exists" one: `stage-vendor.py:72` (config skip), `:92`
  (not-vendored), `:104` (spec failed), `:132` (tarball exists), `:144` (vendor-store
  hit) -> inconsistent stage rows. Decide first whether a `log` pointing at an empty
  file is better than `NULL` for the report renderer [P2/D1]
- #BUG-0097 no scalar-type validation for `packages.yaml` -- nothing checks that
  a YAML scalar loaded from `packages.yaml` has the type the code assumes.
  `lib/validation.py:11`'s `REQUIRED_FIELDS` checks presence only, so
  `version: 1.9` (a float) passed both validators until it was found by hand and
  fixed 2026-08-28 (see `docs/CHANGELOG.md`). Add a field->type table to
  `lib/validation.py` (`version: str`, `release: int`, `url: str`,
  `source.commit.full: str`) and reject mismatches. The `str()` wrappers now
  littering ~15 call sites are compensation for the absence of this check and can
  start coming out once it exists -- which is why this should land before
  BUG-0093's `TypedDict` work, not after [P2/D2]

### Tests

- #BUG-0055 `tests/test_stage_mock.py::TestOfflineGate::
  test_addrepo_still_added_when_local_repo_has_repodata` fails on a host
  without `createrepo_c` installed (`FileNotFoundError: [Errno 2] No such
  file or directory: 'createrepo_c'`). The test patches `stage_mock.run_cmd`
  and `update_local_repo`, but `regenerate_repo_metadata()`
  (`scripts/stage-mock.py:57-72`) calls `subprocess.run(["createrepo_c", ...])`
  directly rather than through `run_cmd`, so it's never mocked -- the test's
  empty `repodata/` dir trips `stage-mock.py:318-322`'s "repodata is
  empty/corrupt -- regenerating" path, which shells out to the real binary.
  Confirmed pre-existing (fails identically on `main` before/after
  #BUG-0054, via `git stash`); every other test in the suite passes on this
  host (1449 passed, this 1 failed). Normally invisible because `make test`
  runs inside the toolbox container where `createrepo_c` is installed; only
  bites a bare `pytest tests/` on the host. Fix: patch
  `regenerate_repo_metadata` (or the `subprocess.run` call inside it) in the
  test, same as `run_cmd` is patched elsewhere [P3/D1]
- #BUG-0080 `tests/conftest.py`'s `fake_repo` fixture (`:15-77`) writes a
  `packages.yaml` that is not valid YAML: `{\n  valid-pkg:\n    version: ...`
  mixes a flow-mapping open brace with block-style indented content, which
  `yaml.safe_load` rejects (`yaml.parser.ParserError: while parsing a flow
  mapping ... expected ',' or '}', but got ':'`). Never caught before because
  no existing test actually parses this default content via
  `get_packages()`/`load_packages_yaml()` -- every prior `fake_repo` consumer
  either overwrites `packages.yaml` itself first or never calls a YAML-parsing
  function on it. Found while writing `tests/test_pkg_build_pop.py` for
  BUG-0078, worked around there by writing a fresh valid `packages.yaml` in
  each test rather than relying on the fixture default. Fix: drop the leading
  `{`/trailing `}` so the fixture is plain block-style YAML [P2/D1]

### Container / Makefile

- #BUG-0052 `.env` (repo root, gitignored but present on this host) has `SKIP_COPR`
  and `SYNCHRONOUS_COPR_BUILD` each assigned **twice** (`SKIP_COPR=true` at line 18
  then `SKIP_COPR=false` at line 20; `SYNCHRONOUS_COPR_BUILD=true` duplicated
  harmlessly at 17/19) -- found while investigating BUG-0050/BUG-0051, not itself
  the cause of the 2026-09-08 zero-push incident (`full-cycle-matrix`'s
  `matrix-chroot-%` recipe always passes `SKIP_COPR=true` as an explicit
  command-line-style override to the recursive `$(MAKE) full-cycle`, which beats
  any `-include .env` default regardless). Still a live footgun: Make's `-include
  .env` (`Makefile:2`) parses `.env` as Makefile syntax where the *last*
  assignment of a `=` variable wins, so any plain `make full-cycle` (not via the
  matrix) run without an explicit `SKIP_COPR=` on its own command line silently
  defaults to `SKIP_COPR=false` -- the opposite of what line 18's value suggests
  at a glance -- and submits to Copr when the reader of line 18 alone would
  expect it not to. Also stale in the same file: line 9's comment says "(42, 43,
  44, or rawhide)" for `FEDORA_VERSION`, but `SUPPORTED`/`SUPPORTED_FEDORA_VERSIONS`
  have been `43 44 45` since ce1d02de -- neither 42 nor rawhide is valid anymore.
  Fix: de-duplicate `.env`, drop the `false`/second `true` lines, and refresh the
  comment. Same class of bug likely worth a one-time `make`-level lint (warn on a
  repeated key in `.env`) rather than just a manual fix [P3/D1]

- #BUG-0006 `make container-enter` (`Makefile:452-456`) doesn't match
  `$(CONTAINER_RUN)` (`Makefile:98-108`): missing `--privileged`, missing the
  mock-cache/mock-root podman volume mounts (`/var/cache/mock`, `/var/lib/mock` --
  not a config file), missing the `.venv` mount, missing the copr-config mount, and
  missing the `LOG_LEVEL`/`NO_COLOR` env passthrough -> manual mock testing inside
  fails differently than real stages [P3/D1]

- #BUG-0009 Makefile `full-cycle` passes `DRY_RUN` env var into the container but
  nothing in scripts/ reads it (repo-wide grep for `DRY_RUN` under `scripts/` is
  empty) -> silent no-op flag, misleading. `FORCE_REBUILD` is the real flag that
  replaced it (`full-cycle.py:154,219,790`; `stage-show-plan.py:116`;
  `lib/pipeline.py:81-82`), see docs/operations.md [P3/D1]

### Makefile

- #BUG-0071 `delete-package.py:95-97` now cleans the artifacts ledger
  (`build_db.forget_package`, `lib/build_db.py:431-436`) but never touches
  `local-repo/*/<pkg>-*.rpm` -> stale RPMs linger across every target, and are now
  *worse off* than before: they survive on disk with no DB row pointing at them
  anymore. Fix needs a glob-and-unlink plus `regenerate_repo_metadata` per touched
  target, or dnf metadata goes stale [P2/D2]

### Scripts

- #BUG-0072 Ctrl+C is handled inconsistently across the scripts. Confirmed by hand: the
  long-running orchestration scripts already catch it cleanly --
  `full-cycle.py:851-853`, `stage-mock.py:441`, `stage-copr.py:306`, `stage-srpm.py:225`,
  `stage-vendor.py:231`, `stage-spec.py:321`, `stage-validate.py:173`,
  `refresh-checksums.py:120` and `pkg-build-pop.py:54` all wrap
  `main()` in `except KeyboardInterrupt: print(...); sys.exit(130)`. And the
  Makefile layer around them propagates a SIGINT correctly too: the
  `PIPELINE_LOCK_FILE` flock (`Makefile:151-153`) is scoped to the holding
  fd, so it releases itself the instant the shell exits, no manual cleanup
  needed; and `_full-cycle-matrix`'s per-chroot loop (`Makefile` `for v in
  $(MATRIX_ORDERED_VERSIONS) ... || { overall=1; ... }`) does NOT swallow a
  Ctrl+C into "chroot marked failed, loop continues" as the `||` shape might
  suggest -- verified with a standalone repro (`sleep 5 || { ...}` in a
  three-iteration loop, SIGINT sent to the whole process group mid-sleep):
  bash re-raises SIGINT on itself and the whole non-interactive script dies
  outright, `||` notwithstanding, so the remaining matrix chroots are never
  attempted after an interrupt. What's missing: 16 other top-level scripts
  have no `KeyboardInterrupt` handler at all -- `db-artifacts.py`,
  `delete-package.py`, `format-yaml.py`, `gather-requires.py`,
  `gen-readme-shell.py`, `gen-report.py`, `gen-spec.py`, `list-tags.py`,
  `pkg-log-analysis.py`, `rpm-dir-prefixes-convert.py`, `scaffold-package.py`,
  `set-package-release.py`, `sort-yaml-lists.py`, `stage-show-plan.py`,
  `update-versions.py`, `validate-packages.py`. Ctrl+C still stops them (default
  Python behavior), but as a raw traceback and exit code 1, not the clean
  message + exit(130) the rest of the pipeline gives. Most of these are short
  and low-stakes, but `update-versions.py` is the one that actually matters:
  it's the first stage of every `make update-daily` run and serially fetches
  45+ submodules over the network (BUG-0100/-0101), so it's the
  longest-lived script most likely to be interrupted mid-run. Fix: add the
  same `except KeyboardInterrupt: sys.exit(130)` wrapper used everywhere
  else, at minimum to `update-versions.py` [P3/D1]
- #BUG-0079 `lib/yaml_utils.get_packages(path: Path = PACKAGES_YAML)`
  (`lib/yaml_utils.py:118`) binds its default at import time, so a caller that
  invokes it bare -- `set-package-release.py:53`, `pkg-build-pop.py:24` -- is not
  redirected by `tests/conftest.py`'s `fake_repo` fixture monkeypatching
  `lib.paths.PACKAGES_YAML`; both scripts' own tests work around this by also
  patching the script module's `get_packages` reference directly. Found while
  writing tests for BUG-0078. Fix: `get_packages(path: Path | None = None)` with
  `path = path or PACKAGES_YAML` resolved inside the function body [P2/D1]
- #BUG-0082 `set-package-release.py:36`'s `lock = "--lock" in sys.argv` detects
  the flag by membership anywhere in argv, so
  `set-package-release.py --lock hyprlang 5` silently treats `--lock` as the
  package-name positional (`sys.argv[1]`) instead of erroring -- found while
  writing tests for BUG-0078. Switch to real flag parsing (argparse, or at
  least filter `--lock` out of the positionals before indexing) [P3/D1]

## Tech debt

Refactor / typing / dedup / structure with no behavior change.

### Containers / caches

- #BUG-0058 the generator version itself (`gen-spec.py`/`stage-spec.py`) isn't a
  tracked cache input at all -- `compute_input_hashes()` (`lib/cache.py:102-117`)
  covers source_commit/templates/package_config/dependencies/patches/package_version
  only. Report which packages were last built with an older generator version [P3/D2]

### Build report db

Migrated from build-report.yaml to build-report.db (sqlite, stdlib) -- see git
history for the migration. Composite key is now `(package, stage, target)`, row
upserts instead of full-file rewrites, and an `artifacts` table tracks disk usage
(`make db-usage`/`make db-prune`). Remaining gaps:

- #BUG-0059 only "last attempt" is stored per (package, stage, target)
  (`lib/build_db.py:36-56`), not "last success" -> a failed rebuild overwrites the
  previous known-good version/log/build_id, no `last_success` kept alongside
  `last_attempt` [P2/D3]
- #BUG-0061 artifact sha256 to detect corrupted local-repo RPMs (the wrong-chroot
  case is now caught by the per-chroot `local-repo/<target>/` layout; sha256 is still
  needed for on-disk corruption within a target). `artifacts` table
  (`lib/build_db.py:58-69`) has no `sha256` column today; hashing every RPM on every
  run has a real I/O cost, so this needs an mtime/size guard [P2/D3]
- #BUG-0062 `db-shell`/`db-usage`/`db-prune` only resolve correctly inside the
  container (artifact paths are container-absolute); no host-side fallback. Can only
  ever be partial: the `rpmbuild-volume` realm lives in a podman named volume with no
  host path at all, so a fix covers the repo and vendor-store realms only [P3/D3]
- #BUG-0063 `stage_results.reason` (`lib/build_db.py:39`, populated by
  `lib.pipeline.cache_miss_reason()`) only ever holds the *current* run's
  explanation for why a stage ran/cached -- the table's `(package, stage,
  target)` primary key means the next run's `set_stage()`/`finalize_stage()`
  overwrites it in place, same root cause as BUG-0059. `lib/build_db.py`'s
  own module docstring already flags "append-only attempt history" as a
  follow-up. Concrete cost: reconstructing why run N rebuilt a given package
  requires reading `reason` before run N+1 starts, or falling back to
  filesystem evidence (artifact mtimes, log files) once it's gone -- done by
  hand this way investigating why run 64 rebuilt 19 packages
  (`artifact-missing`) plus one dependency cascade, since run 63's per-package
  reasons were already overwritten by the time it was asked about. Fits
  naturally as a small db addition: an append-only `stage_history` table (or
  similar) written alongside the existing upsert, keyed by
  `(package, stage, target, run_id)`, holding at least `state`/`reason`/
  `version`/`completed_at` -- `run_id` already threads through every
  `set_stage()`/`finalize_stage()` call site, so no caller-side plumbing
  needed beyond the extra insert [P2/D2]

### Build matrix (arch / non-fedora distros)

Db key is already `target` (= mock chroot, e.g. fedora-44-x86_64) and `runs` carries
distro/distro_version/arch, so aarch64 and centos need no schema change. The
distro/arch-agnostic build-target work itself is tracked as a feature, not here — see
[COPR-0019](features/COPR-0019-build-target.md) (Planned).

- #BUG-0065 `artifacts` table has no arch column (`lib/build_db.py:58-69`); a noarch
  subpackage's arch != its target's arch. Best folded into BUG-0061's schema
  migration rather than done separately [P3/D4]

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
- #BUG-0078 3 top-level scripts have zero tests (re-verified 2026-09-14; membership
  changed -- `format-yaml.py`, `pkg-build-pop.py`, `set-package-release.py`, and
  `sort-yaml-lists.py` are now tested and drop off this list (see docs/CHANGELOG.md
  2026-09-14's Phase 1); `serve.py` is removed from the repo and drops off too):
  `gather-requires.py`, `gen-readme-shell.py`, `list-tags.py`
  -> violates the coverage rule now stated in `docs/CONTRIBUTING.md` "Code quality
  and linting". `gather-requires`/`list-tags` have Makefile-level `make -n`
  coverage only (`tests/integration/test_make_targets.py:583,605-616`), which never
  executes the script; all three need a network or subprocess fake (`rpm`,
  `git ls-remote`, or the jinja/git-log pair) rather than being pure-logic
  [P2/D3]
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

- #BUG-0098 `lib/cache.py:_content_hash()` (`:25-35`) and `_package_config_hash()`
  (`:70-79`) are byte-identical implementations -- both drop `release`, normalize
  keys, then sha256 of `json.dumps(..., sort_keys=True, default=str)` -- and
  `compute_input_hashes()` stores both results, under `content` *and*
  `package_config`. Two names, one hash, stored twice in every stage row. Collapsing
  them changes the `hashes` dict shape, and `hashes_match()` (`lib/cache.py:120-123`)
  is an exact dict comparison -- so this invalidates every cached row and forces a
  full 49-package rebuild on the next run. That cost, not the ~15 LOC saved, is the
  real content of this entry [P3/D2]
- #BUG-0101 add concurrency (e.g. `ThreadPoolExecutor`) to `update-versions.py`'s
  per-submodule pull/fetch loop -- split out from BUG-0100 because it's a different
  risk profile (shared `.git/modules` state) from the reporting fix [P3/D3]

## Chores

Mechanical maintenance: pinning, renames, dead-code removal, small tooling additions.

### Build report db

- #BUG-0060 export sqlite -> yaml/json snapshot for offline diffing (`make
  db-export`) -- no such mode exists in `db-artifacts.py` today [P3/D1]

### Makefile

- #BUG-0068 `HIGHLIGHT_PREFIX` default (`Makefile:13`) bakes literal quote chars into
  the value as a hack so unquoted `echo $(HIGHLIGHT_PREFIX) "text"` works;
  check-image/check-venv/setup-volumes instead embed it inside a quoted string ->
  fragile, one edit away from breaking output. Touches ~80+ echo sites across the
  Makefile -- simplify to plain value + consistent quoting everywhere [P3/D1]

### Scripts

- #BUG-0073 `scripts/validate-packages.py` (the `make pre-commit` gate) has no check
  that `docs/BUGS.md`/`docs/TODO.md` are internally consistent -- specifically, that
  no `#BUG-NNNN`/`#TODO-NNNN` ID is declared twice within a file (the exact class of
  bug the 2026-08-18 grooming pass found and fixed by hand: two prior TODO entries had
  been silently reallocated after deletion, and a stale `## Next` section was
  duplicating BUG-0018). Add a check (either in `validate-packages.py` alongside its
  other doc-adjacent checks, or a small standalone script wired into `make
  pre-commit`/`make lint`) that greps both files for `^- #(BUG|TODO)-[0-9]+`
  declarations and fails on any duplicate. Cheap and mechanical -- the exact grep is
  already in the 2026-08-18 grooming session's verification steps [P2/D1]
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
- #BUG-0081 `format-yaml.py:get_formatting_rules()` (`:63-97`) computes
  `indent_spaces` from `.yamllint`'s `indentation` rule, but
  `format_yaml_file()` (`:121-166`) never reads it -- it calls
  `detect_indentation(content)` on the file's own existing content instead
  (`:142`). Dead config path; found while writing tests for BUG-0078.
  Either wire `indent_spaces` in as a fallback when detection is ambiguous, or
  drop it from `get_formatting_rules()`'s return value [P3/D1]
- #BUG-0085 3 YAML modules mix PyYAML-load and ruamel-dump inconsistently with no doc
  on which to use when: `lib/yaml_config.py` is ruamel-only, `lib/yaml_utils.py` is
  PyYAML-only, `lib/yaml_format.py` mixes both (docstring advertises ruamel but
  `:44`/`:150` call `yaml.safe_load`) -> confusing for newcomers. A docstring in each
  module solves the stated pain more cheaply than consolidating [P3/D1]
- #BUG-0086 dead code: `lib/reporting.badge()` (`reporting.py:159`) *and*
  `badge_short()` (`:141`) are both unused by any script -- neither is imported
  outside `tests/test_reporting.py`; the live badge rendering is the Jinja macro
  `templates/_badge.j2`, unrelated to either function. Also `lib/yaml_utils.py:128`'s
  `load_packages = get_packages` alias has zero references -> remove all three [P3/D1]
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
- #BUG-0096 ruff runs with default rules only -- no `ruff.toml`, so
  `Makefile:287`'s `ruff check scripts/` runs `E,F` alone (same gap `mypy.ini`
  just fixed for mypy). `--select ANN,A,B,PLW,PLR,RUF,SIM,TC,FBT,N` reports 231
  findings, several of them variable-lifetime bugs rather than style: `PLW2901`
  redefined-loop-name x8 (`format-yaml.py:54`, `gather-requires.py:56`,
  `gen-spec.py:46,187,421`, `lib/config.py:62`, `lib/github.py:197`,
  `lib/yaml_format.py:68`), `RUF059` unused unpacked variable x2 (`lib/copr.py:95`,
  `update-versions.py:390`), `B904` x2, `B905` x1 (`gen-report.py:286`). Select
  `B,RUF,SIM` plus the useful `PLW` subset; leave `PLR0912/0913/0915` and `N999`
  off -- they fire on the known-large files already tracked as BUG-0076/-0083 and
  on the intentional `kebab-case.py` script names [P3/D2]

### Daily update

- #BUG-0102 `lib/yaml_utils.write_yaml_preserving_comments()`
  (`lib/yaml_utils.py:229-238`) does not preserve comments -- its own docstring says
  so ("accepted trade-off for simpler code"), contradicting the function name.
  Misleading name on the function that rewrites packages.yaml on every nightly run.
  Rename, e.g. to `update_package_versions()` [P3/D1]

### Docs

- #BUG-0103 `docs/DOCS-DRIVEN-DEVELOPMENT.md`'s Rules require every top-level
  function/class implementing a feature to carry the `#COPR-NNNN` IDs it implements,
  as a comment directly above it or the first docstring line. Not yet applied
  anywhere in `scripts/`/`scripts/lib/` -- deliberately out of scope for the DDD
  adoption change itself (essentially every top-level function in the codebase),
  filed here so it isn't forgotten [P3/D4]
