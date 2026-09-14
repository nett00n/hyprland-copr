# Todo

Cleanup, complexity, and unbuilt features. Automation behaving wrong today goes in
`docs/bugs.md` instead. Entries are deleted when done (the fix gets a
`docs/CHANGELOG.md` bullet); IDs are never reused or renumbered, so deletions leave
gaps. Next free ID: **TODO-0094**.

Each entry ends with a `[P#/D#]` marker:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Unsorted

Not investigated enough to file properly: no verified root cause, no priority, no
difficulty. Move an entry into a real section below once it has all three.

- #TODO-0010 separate prod builds and local debug ones (?) -- no stated problem or
  acceptance criterion yet
- #TODO-0013 #2.0 split management system and hyprland repo content, make automations
  repo a submodule of content repo (?) -- a repo-topology decision, not a task, until
  someone rules on it

## Features

- #TODO-0008 add ARM64 local build support. We did not encounter arch-tangled errors.
  Yet [P3/D4]
- #TODO-0009 add cross-os-version build matrix visualization [P3/D4]
- #TODO-0011 add `make fmt` after scaffolding [P3/D1]

## Containers / caches

- #TODO-0073 `_templates_hash()` (`lib/cache.py:65-67`) hashes `spec.j2` and
  `hashes_match()` (`lib/cache.py:120-123`) is a strict full-dict equality, so any
  edit to `spec.j2` invalidates all 49 packages' caches at once and force-rebuilds
  everything. Wanted instead: inform that a cached package's spec was generated from
  an outdated template, rather than force a rebuild [P2/D3]
- #TODO-0076 the generator version itself (`gen-spec.py`/`stage-spec.py`) isn't a
  tracked cache input at all -- `compute_input_hashes()` (`lib/cache.py:102-117`)
  covers source_commit/templates/package_config/dependencies/patches/package_version
  only. Report which packages were last built with an older generator version [P3/D2]

## Build report db

Migrated from build-report.yaml to build-report.db (sqlite, stdlib) -- see git
history for the migration. Composite key is now `(package, stage, target)`, row
upserts instead of full-file rewrites, and an `artifacts` table tracks disk usage
(`make db-usage`/`make db-prune`). Remaining gaps:

- #TODO-0015 only "last attempt" is stored per (package, stage, target)
  (`lib/build_db.py:36-56`), not "last success" -> a failed rebuild overwrites the
  previous known-good version/log/build_id, no `last_success` kept alongside
  `last_attempt` [P2/D3]
- #TODO-0017 export sqlite -> yaml/json snapshot for offline diffing (`make
  db-export`) -- no such mode exists in `db-artifacts.py` today [P3/D1]
- #TODO-0018 artifact sha256 to detect corrupted local-repo RPMs (the wrong-chroot
  case is now caught by the per-chroot `local-repo/<target>/` layout; sha256 is still
  needed for on-disk corruption within a target). `artifacts` table
  (`lib/build_db.py:58-69`) has no `sha256` column today; hashing every RPM on every
  run has a real I/O cost, so this needs an mtime/size guard [P2/D3]
- #TODO-0020 `db-shell`/`db-usage`/`db-prune` only resolve correctly inside the
  container (artifact paths are container-absolute); no host-side fallback. Can only
  ever be partial: the `rpmbuild-volume` realm lives in a podman named volume with no
  host path at all, so a fix covers the repo and vendor-store realms only [P3/D3]
- #TODO-0087 `stage_results.reason` (`lib/build_db.py:39`, populated by
  `lib.pipeline.cache_miss_reason()`) only ever holds the *current* run's
  explanation for why a stage ran/cached -- the table's `(package, stage,
  target)` primary key means the next run's `set_stage()`/`finalize_stage()`
  overwrites it in place, same root cause as TODO-0015. `lib/build_db.py`'s
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
- #TODO-0077 when package B depends on A and `is_cached("mock", B, ...)` returns
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
  from BUG-0017 (wrong-artifact-kept pruning) and TODO-0018 (on-disk corruption
  detection) -- this is about a dependency's *existence*, not its integrity [P2/D3]

## Build matrix (arch / non-fedora distros)

Db key is already `target` (= mock chroot, e.g. fedora-44-x86_64) and `runs` carries
distro/distro_version/arch, so aarch64 and centos need no schema change. Everything
else is still fedora+x86_64-only:

- #TODO-0022 `FEDORA_VERSION` is the only env knob; needs a TARGET (or DISTRO+ARCH)
  var. `SUPPORTED`/`mock_chroot()` (`lib/paths.py:37-41`)/`Containerfile` FROM are all
  fedora-hardcoded, and `lib/paths.py:28-29`'s `DISTRO`/`ARCH` are module constants
  imported by every stage. `MOCK_CHROOT` already exists as a per-run override
  (`lib/paths.py:44-48`, read by every stage), so an arbitrary chroot can be forced in
  today -- but `DISTRO`/`ARCH` stay wrong and image/volume names don't follow. This is
  the keystone item for the whole section [P2/D4]
- #TODO-0023 two podman volumes are keyed by Fedora version only, not arch:
  `mock-cache-$(FEDORA_VERSION)`, `mock-root-$(FEDORA_VERSION)` (`Makefile:74-77`) --
  two arches would clobber each other on both. (`rpmbuild` is now a single
  version-independent volume shared by every chroot the one container image builds,
  so it no longer has a per-version name to clash on; `local-repo/` is no longer a
  volume either and is already arch-scoped via its `<target>` layout.) A rename
  orphans every existing volume on every dev machine plus `container-volume-clean`
  (`Makefile:473-491`) [P2/D2]
- #TODO-0024 aarch64 builds need qemu-user-static binfmt or a native runner; mock
  --forcearch is not enough for real cross-arch. Zero `qemu`/`binfmt`/`forcearch`
  references anywhere in the repo today; the only aarch64 awareness is
  `lib/copr.py:282`'s reporting giving up with "not verifiable locally". Mostly a
  multi-day infra decision (host binfmt registration, CI runner), not a code change
  [P1/D4]
- #TODO-0025 packages.yaml has `fedora:` override blocks only (exactly one such block
  exists today, under `hyprland`, at `packages.yaml:378`) -> need distro-agnostic
  override keys, and `lib/version.py:128-130`'s `nvr()` hardcodes the `.fcNN` dist tag
  (centos wants `.el10`). The packages.yaml side is nearly free to migrate today since
  there's only the one block [P3/D4]
- #TODO-0085 the single container image is pinned to one Fedora base (43,
  `Containerfile`), so `rpmbuild -bs` (`stage-srpm.py`) always stamps the physical
  SRPM's own dist tag as `.fc43` regardless of `FEDORA_VERSION` -- confirmed by hand:
  building for target `fedora-45-x86_64` produced
  `hyprutils-0.14.2-2.fc43.src.rpm` on disk while `build-report.db`'s `srpm` row for
  that target records `version=0.14.2-2.fc45` (from `lib.version.nvr()`'s
  target-computed label, `stage-srpm.py:83`). This is cosmetic, not a correctness bug:
  `mock --rebuild`/Copr both re-expand `%{?dist}` from the target chroot's own
  macros regardless of the SRPM's frozen release string -- confirmed by hand too, the
  binary RPMs mock produced for `fedora-45-x86_64` correctly came out `.fc45` -- and
  every cache/artifact check in `lib/pipeline.py` compares the DB's own recorded label
  against itself, never against the literal filename. Still worth fixing so
  `build-report.db`/logs don't show a version string the physical file disagrees
  with; likely means `nvr()` should stop pretending the SRPM's own dist tag is
  target-specific once there's only one canonical build of it [P3/D3]
- #TODO-0026 `artifacts` table has no arch column (`lib/build_db.py:58-69`); a noarch
  subpackage's arch != its target's arch. Best folded into TODO-0018's schema
  migration rather than done separately [P3/D4]
- #TODO-0027 copr rows are keyed by one `target` (`stage-copr.py:73-138` resolve a
  single local `target` per run), but COPR fans out to its own chroots -> a real
  matrix needs copr rows keyed by the COPR chroot instead. Needs a `copr_chroot`
  dimension in `stage_results` (or a separate table), plus `fetch_failed_chroot_logs`/
  `print_chroot_coverage` rework. Do together with TODO-0018/TODO-0026's schema bump.
  Still open after the per-package Copr gate (`lib.copr.ineligible_packages()`): that
  gate reads per-chroot *mock* rows (already correctly per-chroot), not the copr
  stage's own single row, so it sidesteps this rather than fixing it [P2/D4]
- #TODO-0028 gen-report/templates assume one target per report
  (`gen-report.py:251`'s `run.fedora_version`, consumed by
  `templates/full-report.md.j2:8`); a matrix view needs a package x target grid.
  Blocked on TODO-0027 for the copr column to mean anything [P3/D4]

## Makefile

- #TODO-0030 two different multi-package loop strategies coexist: Makefile-side
  `_PKGS` loop (`Makefile:123`, used by `sources` and `stage-log-analyze`) vs
  pass-PACKAGE-to-python (every `stage-*` target) -> pick one [P3/D1]
- #TODO-0086 `full-cycle-matrix`'s `matrix-chroot-%` targets (`Makefile`) build every
  chroot in `MATRIX_VERSIONS` serially via a plain shell `for` loop in
  `_full-cycle-matrix` (was `$(MAKE) -k` plus an order-only prerequisite until
  docs/bugs.md BUG-0053's fix), even though the chroots are
  independent once the canonical one has run. `-j` isn't supported: the canonical
  chroot's release-bump step (`SKIP_RELEASE_BUMP`, BUG-0049) writes the shared
  `packages.yaml` while every other chroot's `full-cycle` call reads it, and the
  pipeline `flock` (BUG-0043) refuses a second concurrent `make` invocation by
  design anyway -- both would need solving first [P3/D3]
- #TODO-0031 `HIGHLIGHT_PREFIX` default (`Makefile:13`) bakes literal quote chars into
  the value as a hack so unquoted `echo $(HIGHLIGHT_PREFIX) "text"` works;
  check-image/check-venv/setup-volumes instead embed it inside a quoted string ->
  fragile, one edit away from breaking output. Touches ~80+ echo sites across the
  Makefile -- simplify to plain value + consistent quoting everywhere [P3/D1]
- #TODO-0032 `ALL_PACKAGES` (`Makefile:118`) parses packages.yaml with a grep regex
  instead of the yaml lib used everywhere else -> fragile, switch to yaml. Caveat:
  it's a `$(shell)` evaluated at parse time on *every* make invocation, so a naive
  swap to python adds interpreter startup to every target -- needs a cache, not a
  straight swap [P2/D1]
- #TODO-0033 `add-submodule`/`add-new` still embed real logic (yaml edits, git
  submodule surgery) directly in Makefile recipes (`Makefile:330-349`) instead of
  scripts/*.py -> untestable by pytest. `delete-package` still holds submodule surgery
  and the volume sweep in the recipe after its script call (`Makefile:356-376`).
  `scaffold-package` is already done -- it fully delegates to
  `scripts/scaffold-package.py`, which is tested [P2/D3]
- #TODO-0035 `delete-package.py:95-97` now cleans the artifacts ledger
  (`build_db.forget_package`, `lib/build_db.py:431-436`) but never touches
  `local-repo/*/<pkg>-*.rpm` -> stale RPMs linger across every target, and are now
  *worse off* than before: they survive on disk with no DB row pointing at them
  anymore. Fix needs a glob-and-unlink plus `regenerate_repo_metadata` per touched
  target, or dnf metadata goes stale [P2/D2]

## Scripts

- #TODO-0089 Ctrl+C is handled inconsistently across the scripts. Confirmed by hand: the
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
  45+ submodules over the network (TODO-0068/-0075), so it's the
  longest-lived script most likely to be interrupted mid-run. Fix: add the
  same `except KeyboardInterrupt: sys.exit(130)` wrapper used everywhere
  else, at minimum to `update-versions.py` [P3/D1]
- #TODO-0078 `scripts/validate-packages.py` (the `make pre-commit` gate) has no check
  that `docs/bugs.md`/`docs/todo.md` are internally consistent -- specifically, that
  no `#BUG-NNNN`/`#TODO-NNNN` ID is declared twice within a file (the exact class of
  bug the 2026-08-18 grooming pass found and fixed by hand: TODO-0062/0063 had been
  silently reallocated after deletion, and `## Next` was duplicating BUG-0018). Add a
  check (either in `validate-packages.py` alongside its other doc-adjacent checks, or
  a small standalone script wired into `make pre-commit`/`make lint`) that greps both
  files for `^- #(BUG|TODO)-[0-9]+` declarations and fails on any duplicate. Cheap and
  mechanical -- the exact grep is already in the 2026-08-18 grooming session's
  verification steps [P2/D1]
- #TODO-0036 `scripts/gen-spec.py` (446 lines) duplicates `lib/github.py`
  (`_cache_key`/`load_release_cache`/`save_release_cache`/`fetch_github_release`/
  `build_changelog`) and `lib/config.get_packager` almost verbatim, has no Makefile
  target, unused except by its own test -> looks like a dead pre-pipeline prototype,
  remove or replace with lib calls. Check first whether `build_context()`
  (`gen-spec.py:210-380`) has spec-rendering logic `stage-spec.py` lacks before
  deleting [P3/D4]
- #TODO-0038 `tests/conftest.py` and `tests/integration/conftest.py` are ~93%
  identical (36-line diff across 96/102-line files) -- real differences are just a
  docstring, a path-depth difference, and one extra `monkeypatch_cwd` fixture -> dedupe
  down to that one fixture [P3/D1]
- #TODO-0039 `scripts/full-cycle.py:run_build_pipeline` is 425 lines
  (`full-cycle.py:267-691`, grown from ~320) of repeated per-stage orchestration
  (spec/vendor/srpm/mock/copr all same shape: cache check -> run_for_package ->
  build_db.finalize_stage) -> candidate for a small stage-runner abstraction. Do
  together with TODO-0040 -- same file family, same shape [P3/D4]
- #TODO-0040 each `stage-*.py` (validate/spec/vendor/srpm/mock/copr) copy-pastes its
  own "config: skip" `set_stage()` call (~6 lines x6, e.g. `stage-srpm.py:76-81`,
  `stage-vendor.py:70-75`) -> extract to a small helper (the old `lib/stage_utils.py`
  was removed in the sqlite migration; a new home is needed, e.g.
  `lib/stage_common.py`) [P3/D1]
- #TODO-0041 3 top-level scripts have zero tests (re-verified 2026-09-14; membership
  changed -- `format-yaml.py`, `pkg-build-pop.py`, `set-package-release.py`, and
  `sort-yaml-lists.py` are now tested and drop off this list (see docs/CHANGELOG.md
  2026-09-14's Phase 1); `serve.py` is removed from the repo (formerly TODO-0048)
  and drops off too): `gather-requires.py`, `gen-readme-shell.py`, `list-tags.py`
  -> violates the coverage rule now stated in `docs/CONTRIBUTING.md` "Code quality
  and linting". `gather-requires`/`list-tags` have Makefile-level `make -n`
  coverage only (`tests/integration/test_make_targets.py:583,605-616`), which never
  executes the script; all three need a network or subprocess fake (`rpm`,
  `git ls-remote`, or the jinja/git-log pair) rather than being pure-logic
  [P2/D3]
- #TODO-0090 `lib/yaml_utils.get_packages(path: Path = PACKAGES_YAML)`
  (`lib/yaml_utils.py:118`) binds its default at import time, so a caller that
  invokes it bare -- `set-package-release.py:53`, `pkg-build-pop.py:24` -- is not
  redirected by `tests/conftest.py`'s `fake_repo` fixture monkeypatching
  `lib.paths.PACKAGES_YAML`; both scripts' own tests work around this by also
  patching the script module's `get_packages` reference directly. Found while
  writing tests for TODO-0041. Fix: `get_packages(path: Path | None = None)` with
  `path = path or PACKAGES_YAML` resolved inside the function body [P2/D1]
- #TODO-0093 `tests/conftest.py`'s `fake_repo` fixture (`:15-77`) writes a
  `packages.yaml` that is not valid YAML: `{\n  valid-pkg:\n    version: ...`
  mixes a flow-mapping open brace with block-style indented content, which
  `yaml.safe_load` rejects (`yaml.parser.ParserError: while parsing a flow
  mapping ... expected ',' or '}', but got ':'`). Never caught before because
  no existing test actually parses this default content via
  `get_packages()`/`load_packages_yaml()` -- every prior `fake_repo` consumer
  either overwrites `packages.yaml` itself first or never calls a YAML-parsing
  function on it. Found while writing `tests/test_pkg_build_pop.py` for
  TODO-0041, worked around there by writing a fresh valid `packages.yaml` in
  each test rather than relying on the fixture default. Fix: drop the leading
  `{`/trailing `}` so the fixture is plain block-style YAML [P2/D1]
- #TODO-0091 `format-yaml.py:get_formatting_rules()` (`:63-97`) computes
  `indent_spaces` from `.yamllint`'s `indentation` rule, but
  `format_yaml_file()` (`:121-166`) never reads it -- it calls
  `detect_indentation(content)` on the file's own existing content instead
  (`:142`). Dead config path; found while writing tests for TODO-0041.
  Either wire `indent_spaces` in as a fallback when detection is ambiguous, or
  drop it from `get_formatting_rules()`'s return value [P3/D1]
- #TODO-0092 `set-package-release.py:36`'s `lock = "--lock" in sys.argv` detects
  the flag by membership anywhere in argv, so
  `set-package-release.py --lock hyprlang 5` silently treats `--lock` as the
  package-name positional (`sys.argv[1]`) instead of erroring -- found while
  writing tests for TODO-0041. Switch to real flag parsing (argparse, or at
  least filter `--lock` out of the positionals before indexing) [P3/D1]
- #TODO-0042 `lib/log_analysis.py` is 1257 lines (re-verified 2026-08-18, grown from
  944) of ~41 copy-pasted `if m: issues.append(...); continue` blocks from
  hand-written regexes -> a data table of (regex, formatter) pairs would cut it by
  half+. Well covered by `tests/test_log_analysis.py` +
  `tests/test_log_analysis_gaps.py`, making this an unusually safe refactor [P3/D4]
- #TODO-0043 `vendor_golang.py`/`vendor_rust.py` hand-roll subprocess+log-writing
  instead of using `lib/subprocess_utils.run_cmd`, which already does exactly that.
  Both files are tested, so this is safe; watch `vendor_rust.py:62`'s probe call,
  whose semantics may not map cleanly onto `run_cmd`'s return shape [P2/D2]
- #TODO-0045 3 YAML modules mix PyYAML-load and ruamel-dump inconsistently with no doc
  on which to use when: `lib/yaml_config.py` is ruamel-only, `lib/yaml_utils.py` is
  PyYAML-only, `lib/yaml_format.py` mixes both (docstring advertises ruamel but
  `:44`/`:150` call `yaml.safe_load`) -> confusing for newcomers. A docstring in each
  module solves the stated pain more cheaply than consolidating [P3/D1]
- #TODO-0046 dead code: `lib/reporting.badge()` (`reporting.py:159`) *and*
  `badge_short()` (`:141`) are both unused by any script -- neither is imported
  outside `tests/test_reporting.py`; the live badge rendering is the Jinja macro
  `templates/_badge.j2`, unrelated to either function. Also `lib/yaml_utils.py:128`'s
  `load_packages = get_packages` alias has zero references -> remove all three [P3/D1]
- #TODO-0049 `scripts/pkg-log-analysis.py:6-15` imports eight underscore-prefixed
  "private" functions directly from `lib.log_analysis`, and redefines
  `HIGHLIGHT_PREFIX` locally (`:18`) as a third copy of that constant -> either make
  the functions public API or move this script's logic into lib/. Best done together
  with TODO-0042, since that refactor changes these function boundaries anyway [P3/D2]
- #TODO-0050 `Containerfile:9-21` installs cargo/golang/mock/rpmlint with no version
  pins, and the base image tag (`Containerfile:3`) floats too -> minor reproducibility
  risk over time. Pinning individual packages against a floating Fedora base just
  creates dnf resolution failures the moment the base updates; the honest fix is
  digest-pinning the base image itself [P3/D2]
- #TODO-0052 vendoring is triggered by `build_requires` containing `golang`/`cargo`
  (`lib/vendor.py:26-38`, two sources of truth with packages.yaml's Source1 + `tar xf
  %{SOURCE1}`, which must be hand-added and isn't cross-validated) -> silent breakage
  if the pair drifts. No cross-validation exists in `validate-packages.py` or
  `lib/validation.py` today [P2/D2]
- #TODO-0056 `_log_fn` in `lib/vendor.py` is underscore-private but imported directly
  by `vendor_golang.py:9`/`vendor_rust.py:14` (`_download`/`_extract` no longer have
  external importers as of 2026-08-18, so this is now `_log_fn` only). Naturally
  resolved by TODO-0043 -- moving those modules to `run_cmd` removes the need for it
  [P3/D1]
- #TODO-0057 `_download()` in `lib/vendor.py:77-80` reads the whole archive into
  memory (`dest.write_bytes(resp.read())`) instead of streaming to disk with
  `shutil.copyfileobj`. `verify_download()` runs right after
  (`lib/vendor.py:87,168`), so streaming doesn't weaken the checksum guarantee [P2/D1]
- #TODO-0058 vendor stage's `log` field is missing from 5 skip paths, not just the
  "tarball already exists" one: `stage-vendor.py:72` (config skip), `:92`
  (not-vendored), `:104` (spec failed), `:132` (tarball exists), `:144` (vendor-store
  hit) -> inconsistent stage rows. Decide first whether a `log` pointing at an empty
  file is better than `NULL` for the report renderer [P2/D1]
- #TODO-0079 every record in the codebase is an unparameterized `dict` -- 134 bare
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
- #TODO-0080 stage and state names are magic strings across 16 files.
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
- #TODO-0081 `Any` laundered through annotated signatures -- a function annotated
  `-> str | None` / `-> dict` / `-> bool` returning a raw `yaml.safe_load` /
  `json.loads` / `.get()` result. Unlocks mypy's `warn_return_any` (17 errors on
  the current tree; left off in `mypy.ini` pending this). Worst are the trust
  boundaries: `lib/yaml_utils.py:33`, `lib/github.py:54,121`. The annotation is
  the fake here -- the caller sees `str`, the value is `Any`. Fix: typed loader
  wrappers that validate at the parse boundary, after which the annotations
  become true. `gen-spec.py:410`'s `url_to_submodule: dict[str, object]` is the
  same tell in the other direction -- values are `Path`, declared `object`, and
  the parameter receiving it (`gen-spec.py:214`) is a bare `dict` [P2/D3]
- #TODO-0082 ruff runs with default rules only -- no `ruff.toml`, so
  `Makefile:287`'s `ruff check scripts/` runs `E,F` alone (same gap `mypy.ini`
  just fixed for mypy). `--select ANN,A,B,PLW,PLR,RUF,SIM,TC,FBT,N` reports 231
  findings, several of them variable-lifetime bugs rather than style: `PLW2901`
  redefined-loop-name x8 (`format-yaml.py:54`, `gather-requires.py:56`,
  `gen-spec.py:46,187,421`, `lib/config.py:62`, `lib/github.py:197`,
  `lib/yaml_format.py:68`), `RUF059` unused unpacked variable x2 (`lib/copr.py:95`,
  `update-versions.py:390`), `B904` x2, `B905` x1 (`gen-report.py:286`). Select
  `B,RUF,SIM` plus the useful `PLW` subset; leave `PLR0912/0913/0915` and `N999`
  off -- they fire on the known-large files already tracked as TODO-0039/-0042 and
  on the intentional `kebab-case.py` script names [P3/D2]
- #TODO-0083 no scalar-type validation for `packages.yaml` -- nothing checks that
  a YAML scalar loaded from `packages.yaml` has the type the code assumes.
  `lib/validation.py:11`'s `REQUIRED_FIELDS` checks presence only, so
  `version: 1.9` (a float) passed both validators until it was found by hand and
  fixed 2026-08-28 (see `docs/CHANGELOG.md`). Add a field->type table to
  `lib/validation.py` (`version: str`, `release: int`, `url: str`,
  `source.commit.full: str`) and reject mismatches. The `str()` wrappers now
  littering ~15 call sites are compensation for the absence of this check and can
  start coming out once it exists -- which is why this should land before
  TODO-0079's `TypedDict` work, not after [P2/D2]

## Daily update

Design/complexity items found while auditing `make update-daily` end to end
(2026-08). Automation actually misbehaving from these findings is logged in
docs/bugs.md's `## update-daily` section instead.

- #TODO-0062 `lib/cache.py:_content_hash()` (`:25-35`) and `_package_config_hash()`
  (`:70-79`) are byte-identical implementations -- both drop `release`, normalize
  keys, then sha256 of `json.dumps(..., sort_keys=True, default=str)` -- and
  `compute_input_hashes()` stores both results, under `content` *and*
  `package_config`. Two names, one hash, stored twice in every stage row. Collapsing
  them changes the `hashes` dict shape, and `hashes_match()` (`lib/cache.py:120-123`)
  is an exact dict comparison -- so this invalidates every cached row and forces a
  full 49-package rebuild on the next run. That cost, not the ~15 LOC saved, is the
  real content of this entry [P3/D2]
- #TODO-0063 `full-cycle.py:305-306` unconditionally sleeps 5 seconds after printing
  the build plan "before proceeding" -- an interactive abort window that only burns
  time in the unattended cron flow the target is documented for, and is paid 3x by
  `make full-cycle-matrix` (once per Fedora version). Gate on `sys.stdout.isatty()`
  [P2/D1]
- #TODO-0066 nothing in the daily flow reports what happened beyond a commit message
  containing a timestamp. `update-daily` runs `make stage-log-analyze` after `readme`
  every night (closes BUG-0041 -- that's what puts the analysis before the next run's
  log rmtree), but its output only goes to whatever captures update-daily's stdout
  (cron mail, if configured); there's still no durable nightly summary artifact
  committed or posted anywhere. `pkg-log-analysis.py` is now tested (TODO-0041), which
  makes adding a `--output <file>` mode safer than it used to be [P3/D3]
- #TODO-0068 `update-versions.py` (423 lines) fetches 45+ submodules serially on
  every run, and 10 separate warn-and-continue sites
  (`update-versions.py:118,125,137,150,188,327,335,344,361,375`) print individual
  failures to stderr with nothing aggregated -> a single `git fetch` failure is
  invisible in the stdout summary, so a package can silently sit on a stale version
  indefinitely. Scoped down to just the aggregate-failure-report half; see
  #TODO-0075 for the concurrency half, split out separately since it's materially
  riskier (git operations on shared `.git/modules`) [P2/D2]
- #TODO-0075 add concurrency (e.g. `ThreadPoolExecutor`) to `update-versions.py`'s
  per-submodule pull/fetch loop -- split out from TODO-0068 because it's a different
  risk profile (shared `.git/modules` state) from the reporting fix [P3/D3]
- #TODO-0069 `lib/yaml_utils.write_yaml_preserving_comments()`
  (`lib/yaml_utils.py:229-238`) does not preserve comments -- its own docstring says
  so ("accepted trade-off for simpler code"), contradicting the function name.
  Misleading name on the function that rewrites packages.yaml on every nightly run.
  Rename, e.g. to `update_package_versions()` [P3/D1]

## Source verification

`sources.lock.yaml` (docs/packaging.md "Source verification", closes docs/bugs.md
BUG-0025) pins a sha256 per remote source but does not check any signature.
Deliberately deferred, not designed here:

- #TODO-0070 no GPG/detached-signature verification. Would need a per-package
  `source.gpg_key` (key ID or fingerprint) plus fetching the matching `.asc`/`.sig`
  next to the archive, and a repo-local keyring to import trusted keys into (out of
  scope: which keyserver, TOFU-vs-pinned key trust, and revocation are all separate
  design questions). Moot for the current package set today -- 43/45 sources are
  GitHub auto-generated tag archives, which GitHub does not sign; only worth building
  once a package with a real upstream-signed release shows up [P3/D4]
- #TODO-0071 for upstreams that sign git tags (not the same thing as a signed release
  tarball), `git tag -v <tag>` inside the submodule checkout would verify the tag
  itself before `update-versions.py` records its commit. The submodule-init blocker
  this entry used to cite is gone: `Makefile:166-168` (`submodules-update`) and
  `full-cycle.py:88-110`'s `preflight_autoheal()` both already init missing
  submodules unconditionally. Remaining substance is only that `git tag -v`
  verification itself isn't implemented [P3/D3]
- #TODO-0088 build logs are only ever kept for the most recent run: `get_package_log_dir()`
  (`lib/paths.py:42-44`) resolves to a flat `logs/build/<pkg>/` with no run identifier, and
  `update-daily` rmtrees that tree before each night's run (BUG-0041's ordering fix
  runs `make stage-log-analyze` first specifically so this rmtree doesn't eat the
  logs before they're read once) -- so a failure from two nights ago is simply gone,
  there is nothing to diff a flaky failure across runs with, and (per TODO-0074) an
  f43 and f44 build of the same package already overwrite each other's logs today
  since there's no distro/version segment either. Wanted: nest under both a run
  identifier and the target chroot, e.g. `logs/<run_id>/<distro>-<version>/<package>/`,
  so `make update-daily`'s nightly summary (TODO-0066) can link back to the exact
  per-run, per-os-version log instead of whatever happens to be on disk right now.
  Needs a retention/prune policy alongside it (unbounded per-run dirs will otherwise
  grow logs/ forever) and should land together with TODO-0074's distro/version
  restructure rather than doing the path layout twice [P2/D3]
- #TODO-0074 mock's three logs (`build.log`/`root.log`/`state.log`) still copy out of
  the `/var/lib/mock` podman-volume resultdir after the fact
  (`stage-mock.py:184-190`'s `copy_mock_results()`) instead of being bind-mounted, so
  they can't be tailed live -- the repo itself is already bind-mounted
  (`Makefile:75`'s `WORKDIR_MOUNT`), so this is specifically mock's own resultdir.
  Separately, log dirs still lack a distro/version segment
  (`lib/paths.py:16-17,32-34`'s flat `logs/build/<pkg>`), so an f43 and f44 build of
  the same package overwrite each other's logs -- fix by following a
  `./logs/<distro>/<version>/<package>/` pattern. The relative-path display half of
  this is already done (`stage-mock.py:191,345-348`). Live-tailing mock is the cheap
  win; the distro/version restructure is the bigger one -- treat as two separate
  changes [P2/D3]
