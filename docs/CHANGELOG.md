# Changelog

Tracks changes to this repo's automation - Makefile targets, script behavior,
`packages.yaml` schema, build pipeline stages, breaking contributor-facing
changes. Routine package adds/version bumps/release increments are NOT logged
here (see `packages.yaml` git history, `docs/full-report.md`, or `blog/`
instead).

Newest first. One `## YYYY-MM-DD` section per day with changes; one bullet per
entry as `- <Added|Changed|Fixed|Removed>: <what changed>`. Full ruleset in
`docs/CONTRIBUTING.md` "Changelog".

History before this file's introduction is not backfilled - see `git log`.

## 2026-09-09

- Fixed: `make stage-validate` now exits non-zero when any single package fails
  validation, not just on global checks (group membership/duplicate URLs/
  `.gitmodules`). `stage-validate.py`'s per-package loop discarded
  `run_for_package()`'s bool return, so a package with errors (missing
  required field, invalid `depends_on`, bad `fedora:` override key, etc.) was
  printed and recorded as a `failed` build-db row but never flipped the run's
  exit code (docs/bugs.md formerly BUG-0054).

- Fixed: `make validate-packages` (the pre-commit gate) and `make stage-validate`
  (the real build's stage 0) now share a single validator (`lib.validation`) instead
  of two independently-diverged ones, so a package can no longer pass one and fail the
  other. Two concrete disagreements fixed as part of the unification: `depends_on`
  reference checking is now case-insensitive everywhere, matching
  `lib.deps.effective_deps` (the actual dependency-DAG resolver) rather than the old
  pre-commit gate's case-sensitive check; and `lib.validation.VALID_FEDORA_OVERRIDE_KEYS`
  now matches `lib.yaml_utils.apply_os_overrides` in only recognizing `fedora: {skip:
  ...}` -- previously `stage-validate` silently accepted a `fedora.<ver>.build`/
  `build_requires`/`requires` override block that the build then silently dropped.
  `scripts/validate-packages.py` is now a thin front-end over `lib.validation`; it also
  gained self-dependency and `.gitmodules` `ignore = dirty` checks in `lib.validation`
  itself (`.gitmodules` parsing's `parse_gitmodules()` now also returns each section's
  `ignore` value). (docs/bugs.md formerly BUG-0012)

## 2026-09-08

- Fixed: `make db-prune` now keeps the highest RPM version-release per
  (package, target, kind) instead of the file with the latest mtime (new
  `lib.version.rpmvercmp`/`compare_evr`) -- a rebuild that produced an older
  version (a pin rollback, a corrected `pinned-version`) used to get a later
  wall-clock mtime and `--prune --confirm` deleted the newer artifact and
  kept the older one, silently and irreversibly. Mtime is now only the
  tiebreaker for equal or unversioned rows (docs/bugs.md BUG-0017).
- Fixed: `make stage-show-plan` (and the plan preview `full-cycle.py` prints
  before every run) now predicts dependency cascades correctly instead of
  showing a dependent package as `cache` when its dependency is about to
  rebuild in the same run. Two causes fixed together: `show_plan()` now walks
  packages in the same topologically-sorted, transitive-deps-expanded order
  as the real run (new `lib.deps.ordered_packages()`, shared with
  `full-cycle.py`'s `prepare_packages()`, which now delegates to it), and it
  threads a `would_rebuild: set[str]` accumulator through the loop instead of
  passing a fresh `set()` to `compute_forced_stages()` per package, mirroring
  `full-cycle.py`'s own growing `rebuilt_packages` (docs/bugs.md BUG-0048).
- Fixed: `stage-copr.py` now fails loud (non-zero exit, unmissable stderr
  summary) when a locally-buildable Copr chroot has zero verified/skipped
  packages -- a "blackout" chroot, new `lib.copr.blackout_chroots()` --
  because that silently holds back every package in the run. Previously
  `ineligible_packages()`'s per-package gate filtered all of them out before
  the submission loop and the script exited 0 with nothing submitted and no
  signal why (docs/bugs.md BUG-0051, fixed -- the last open item from the
  2026-09-07/08 zero-push incident, see BUG-0050/BUG-0053 above). The gate
  fires only on a genuine coverage gap, not merely "everyone happened to be
  held back this run" (e.g. a real mock failure and its dependents) --
  `print_chroot_coverage()`'s table now also calls out a blackout chroot by
  name. `ALLOW_EMPTY_COPR_SUBMISSION=true` opts out for a deliberate
  nothing-to-submit run. `docs/operations.md` documents backfilling a new
  `SUPPORTED_FEDORA_VERSIONS` entry with `make matrix-chroot-<N>` before its
  first nightly, to avoid hitting this on a version's first night.
- Fixed: the six standalone `stage-*` Makefile targets (`stage-validate`,
  `stage-spec`, `stage-vendor`, `stage-srpm`, `stage-mock`, `stage-copr`) now
  forward `PROCEED_BUILD` into the container's `env`, matching `_full-cycle`.
  Previously `make stage-mock PACKAGE=X PROCEED_BUILD=true` silently ran in
  non-proceed mode, and `lib.yaml_utils.prepare_stage()` cleared that stage's
  `build-report.db` rows for the packages being built even though the
  operator explicitly opted out of that (docs/bugs.md BUG-0016).
- Changed: Copr submission is now gated per package instead of all-or-nothing.
  `lib.copr.ineligible_packages()` holds back any package not yet `verified`
  (or deliberately `skipped`) on every locally-buildable chroot -- the new
  `COVERAGE_SKIPPED` coverage verdict, and a new `local_chroots()` helper that
  fixes a real deadlock: `chroot_coverage()` used to call any same-arch
  chroot outside `SUPPORTED_FEDORA_VERSIONS` (e.g. a Copr project still
  listing `fedora-rawhide-x86_64` after the matrix dropped it, docs/todo.md
  TODO-0085's neighbor) `unbuilt` rather than `unverifiable`, which would have
  permanently blocked every package under the new strict gate. `lib.copr`
  also gained `block_transitive_dependents()`, the dependency-cascade
  primitive `copr_blocked_packages()` (full-cycle.py's per-target gate) was
  refactored onto; `stage-copr.py`'s `main()` -- the standalone entry point
  `full-cycle-matrix` submits through, which previously held back a
  package's own srpm/mock failure but never its dependents' -- now calls it
  directly over `ineligible_packages()`'s result, spanning every chroot in
  the matrix rather than one target. `stage-copr.py` also now reads the
  submission SRPM from the canonical target's `srpm`/`mock` rows
  (`lib.paths.CANONICAL_FEDORA_VERSION`), not the default `FEDORA_VERSION`'s --
  with the rpmbuild volume shared (COPR-0018) both point at the same file
  today, but only the canonical one is guaranteed populated.
  `REQUIRE_CHROOT_COVERAGE`'s existing all-or-nothing abort is unchanged but
  now largely redundant. See docs/FRD.md COPR-0017, docs/operations.md
  "`full-cycle` flags".
- Fixed: `full-cycle-matrix` no longer bumps a package's release once per
  matrix chroot. `update_package_releases()` decides "needs a rebuild" from
  the *spec* stage's row for its own `target` (`lib/yaml_utils.py`'s
  `update_package_releases`), which is per-chroot -- so calling it on every
  `full-cycle FEDORA_VERSION=<v>` in the matrix loop (as `update-daily`
  switching to `full-cycle-matrix` newly does, see the 2026-09-07 section
  below) found no row for the second and third chroot and bumped the release
  again each time, rewriting the shared `packages.yaml` up to three times a
  night. New `SKIP_RELEASE_BUMP` env flag (`full-cycle.py`), set to `true` by
  `full-cycle-matrix` for every chroot except `CANONICAL_FEDORA_VERSION` --
  the release step now runs exactly once per matrix run regardless of how
  many chroots are in `MATRIX_VERSIONS` (and not at all if `MATRIX_VERSIONS`
  excludes the canonical version). Fixes #BUG-0049.
- Changed: `full-cycle-matrix` no longer aborts the whole matrix run the
  moment one chroot fails. `MATRIX_VERSIONS` is now expanded into real
  `matrix-chroot-<version>` targets (a shell `for` loop before, so `make -k`
  had no effect -- it only ever continues across targets) and
  `_full-cycle-matrix` runs them via `$(MAKE) -k`, so a failing chroot no
  longer stops the others. The canonical chroot -- which alone performs the
  release bump (BUG-0049 above) -- is an order-only prerequisite of every
  other chroot target regardless of `MATRIX_VERSIONS`' list order, so it
  always builds first. Copr submission still runs afterward for whatever
  built cleanly (per-package gating unchanged from the 2026-09-08 section
  above); the target's own exit code is nonzero if any chroot failed, which
  `update-daily` already tolerated the same way a plain `full-cycle` failure
  always was. Confirmed by hand: `make full-cycle-matrix PACKAGE=hyprutils
  MATRIX_VERSIONS="43 99 44" COPR_REPO=` -- an invalid `FEDORA_VERSION=99`
  chroot -- ran 43 (canonical) to completion, failed 99, still ran 44 to
  completion, still reached the "COPR_REPO not set" branch, and exited 2
  overall. `-j` (parallel chroots) is deliberately not attempted yet: the
  canonical phase's `packages.yaml` rewrite isn't concurrency-safe against
  the other chroots reading it, and the pipeline `flock` (BUG-0043) refuses
  a second concurrent `make` invocation by design regardless (docs/todo.md
  TODO-0086).
- Fixed: the entry directly above was wrong about `make -k`. `-k` does *not*
  let a target continue past a failed (even order-only) prerequisite -- it
  explicitly refuses to attempt it ("`Target 'matrix-chroot-44' not remade
  because of errors.`", documented GNU Make behaviour, reproduced in an
  isolated sandbox). So for as long as the canonical chroot had any package
  failure -- in practice, `hyprland-plugins` failing to compile against a
  renamed Hyprland symbol (`CWindow::isFloating` -> `m_isFloating`), an
  unrelated real upstream break -- `matrix-chroot-44`/`matrix-chroot-45` were
  silently never attempted at all, three nights running (2026-09-07/08),
  which meant *no chroot but the canonical one ever had real coverage*, which
  meant `lib.copr.ineligible_packages()` (correctly) blocked every package
  from Copr, including ones with no relation to the actual failure (verified:
  `aquamarine` built cleanly on fedora-43 the same run, still held back with
  `blocked: not verified on: fedora-45-x86_64`). Fixed for real this time by
  replacing `make -k`/the order-only prerequisite with a plain shell loop in
  `_full-cycle-matrix` (`for v in $(MATRIX_ORDERED_VERSIONS); do ... || {
  overall=1; ...; }; done`, canonical-first ordering now via
  `$(filter)`/`$(filter-out)` on `MATRIX_VERSIONS` rather than a Make
  prerequisite) that always continues to the next chroot regardless of an
  earlier one's failures. Bundled in the same edit: `stage-copr`'s own exit
  status is now folded into the loop's overall result too, which it
  previously wasn't (`stage-copr` failing outright -- bad credentials,
  `REQUIRE_CHROOT_COVERAGE=true` abort, etc -- used to be invisible to
  `update-daily`'s `|| touch logs/.update-daily-failed` gate as long as the
  local matrix build itself came back clean). Verified: `make
  full-cycle-matrix PACKAGE=hyprutils CANONICAL_FEDORA_VERSION=99
  MATRIX_VERSIONS="99 43 44" COPR_REPO=` now runs 43 and 44 to completion
  despite chroot 99 failing immediately -- the same command against the
  pre-fix Makefile reproduces the original bug verbatim. Fixes #BUG-0053
  (closes #BUG-0050).
- Fixed: a package whose Copr build is still genuinely in progress (state
  `unknown`, non-terminal even after polling) is no longer resubmitted the
  next `full-cycle` run just because `is_cached()` can't tell "in progress"
  apart from "stuck". `run_build_pipeline()`'s copr pass now calls
  `lib.copr.poll_copr_status()` once up front to resolve any build that has
  since finished, then skips resubmission (reason `in-progress`) for any
  package whose row is still `unknown` and has a `build_id` -- unless the
  copr stage itself is forced (force_run, or a dependency rebuilt this run),
  in which case a new version is in play and the old build_id no longer
  applies. Fixes #BUG-0002.

## 2026-09-07

- Changed: `update-daily` now runs `full-cycle-matrix` instead of a single
  `full-cycle` (default `FEDORA_VERSION`), building every `MATRIX_VERSIONS`
  chroot (default all of `SUPPORTED`: 43/44/45) locally before a single
  Copr submission -- roughly triples nightly build time in exchange for
  catching a chroot-specific failure before it reaches Copr instead of only
  after (see docs/bugs.md BUG-0018). Closes TODO-0065.
- Fixed: `full-cycle`'s container recipe now forwards `SKIP_PACKAGES` into
  `full-cycle.py`'s environment (it already forwarded `FORCE_REBUILD`), and
  `full-cycle-matrix`'s per-version loop now forwards both `SKIP_PACKAGES` and
  `FORCE_REBUILD` to its nested `full-cycle` calls. Previously a matrix run
  silently ignored both, and even a plain `full-cycle` run silently ignored
  `SKIP_PACKAGES`. Fixes #BUG-0046.
- Changed: `SUPPORTED` is now `43 44 45` (was `43 44 rawhide`), and the default
  `FEDORA_VERSION` is now `44` (was `43`). `lib.paths.mock_chroot()` and
  `lib.version.nvr()` drop their rawhide special cases -- a `fedora-<N>-x86_64`
  chroot and an `fcN` dist tag are formatted the same way for every supported
  version now, including 45. `FEDORA_VERSION=rawhide`/`MOCK_CHROOT=fedora-rawhide-x86_64`
  still work as a manual override; only the supported matrix changed.
- Changed: the container image is now single and version-independent
  (`Containerfile` no longer takes a `FEDORA_VERSION` build-arg; pinned to Fedora
  43, the oldest `SUPPORTED` version) -- `mock -r` doesn't need a matching host,
  so one image builds every chroot in `SUPPORTED`. `container-build`/`container-all`
  (now an alias)/`container-clean`/`container-enter`/`check-image` all drop their
  per-version image tag. The `rpmbuild` podman volume is likewise now shared
  across every `FEDORA_VERSION` rather than one volume per version, which is what
  makes "one spec, one SRPM" true by construction -- confirmed by hand: a spec and
  SRPM built once for `fedora-43-x86_64` were mock-built as-is into correctly
  `.fc45`-tagged binaries for `fedora-45-x86_64`, with no re-run of `rpmbuild -bs`
  needed for that target's own `stage-mock` to find the SRPM once its own `srpm`
  stage had recorded a row for it. `mock-cache-<ver>`/`mock-root-<ver>` stay
  per-version deliberately (mock already namespaces those internally; see
  docs/todo.md TODO-0023). See docs/FRD.md COPR-0011, docs/todo.md TODO-0085 for a
  related cosmetic bookkeeping gap this surfaced (not a correctness bug).
- Changed: `lib.yaml_utils.apply_os_overrides()` no longer merges a `fedora:`
  override block's `build_requires`/`requires`/`build.*`/`source.patches` into
  the package dict per version -- it only resolves `skip` now.
  `scripts/validate-packages.py` rejects any other key under `fedora:`.
  Confirmed by hand: the repo's only such override (`Hyprland`'s f43-only
  `%prep` sed, previously under `fedora: '43': build: prep:`) was rewritten as
  a literal `%if 0%{?fedora} == 43 ... %endif` block directly in `build.prep`
  -- `stage-spec` now generates byte-identical `packages/hyprland/hyprland.spec`
  content whether run with `FEDORA_VERSION=43` or `44`. See docs/FRD.md
  COPR-0018, docs/packaging.md "Per-Fedora-version spec differences" for the
  idiom.

## 2026-09-06

- Fixed: `update-daily`, `full-cycle`, and `full-cycle-matrix` now take a shared,
  non-blocking `flock` on `logs/.pipeline.lock` before doing any work, and refuse
  (exit non-zero, naming the holder) instead of running concurrently. Previously
  nothing in the repo guarded against two overlapping runs -- a real risk for a
  cron-driven job that can outrun its interval -- writing the same
  `build-report.db`, mock/rpmbuild podman volumes, `local-repo/`, `packages.yaml`,
  and git index, with concurrent `git pull --rebase`/`push` under `PUSH=1` as the
  sharpest edge. `LOCK_DISABLE=1` bypasses the guard deliberately. Fixes #BUG-0043.

## 2026-08-29

- Fixed: `make update-daily` re-runs `validate-packages` (no `fmt`) after
  `full-cycle` and before `readme`/`copr-description`. `full-cycle.py`'s
  `update_package_releases()` rewrites `packages.yaml`'s release fields *after*
  the pre-build `validate-packages`+`fmt` gate has already run, so the file that
  gets committed and rendered into the docs was never re-checked. `fmt` is
  deliberately not re-run: the rewrite already goes through `write_yaml_file`'s
  `FORMAT_FILE`, the same formatter `make fmt` uses, so the file is already
  formatting-clean. Fixes #BUG-0044.
- Changed: `full-cycle.py`'s post-mock Copr-submission gate now blocks only a
  mock-failed package and its transitive dependents, not the whole run. New
  `copr_blocked_packages()` (`full-cycle.py`) replaces the old all-or-nothing
  `blockers` check; a new `lib.deps.reverse_graph()` builds the dependents map
  it walks (also now reused by `topological_sort()`, which built the same
  inversion inline before). Unrelated packages, and a failed package's own
  already-published dependencies, are submitted normally instead of being held
  back. Fixes TODO-0084.

## 2026-08-28

- Fixed: `full-cycle.py`'s `main()` now runs a Copr preflight (new
  `lib.copr.preflight()`, shared with `stage-copr.py`) before any package work and
  exits 2 on a malformed `COPR_REPO` or invalid credentials, instead of discarding
  `check_copr_credentials()`'s return value mid-pipeline. Previously `make
  update-daily COPR_REPO=<typo>` (or an expired token) ran the whole multi-hour
  build for every package before failing. Fixes #BUG-0036.

- Added: `lib.version.recorded_version()`/`versions_for()` compute a display version
  (NVR) per package from the first stage-recorded version across
  spec/srpm/mock/copr, falling back to `packages.yaml`'s declared `version`. Wired
  a `ver=<NVR>` field into `lib.reporting.event()`/`status()` log lines,
  `full-cycle.py`'s `PROCEED_BUILD` resume table and package build plan listing,
  `print_summary()`'s summary table (new `version` column), and
  `report_srpm_failures()`/`report_mock_failures()`/`report_copr_failures()`'s
  per-package failure headers -- so every stage/mock/copr log line and failure
  report now shows which NVR it's talking about instead of leaving readers to
  cross-reference `packages.yaml`.

- Fixed: `poll_copr_status()` (`lib/copr.py`) now matches the full copr-cli
  state vocabulary (`succeeded/failed/canceled/skipped/forked` as terminal;
  `running/starting/pending/importing/waiting` as non-terminal) as whole
  tokens, taking the rightmost match, instead of an unanchored
  `"succeeded"`/`"failed"` substring scan. Previously `canceled`/`skipped`/
  `forked` builds were never recognized and stayed `unknown` forever, getting
  re-polled and resubmitted every night (BUG-0002). An unrecognized status
  now prints a warning instead of silently no-opping. Fixes #BUG-0040.

- Fixed: `poll_copr_status()` (`lib/copr.py`) now `continue`s once a copr-cli status
  token fails to parse, instead of falling through and calling
  `_COPR_TERMINAL_STATE_MAP.get(copr_state)` with `copr_state` still possibly
  `None` -- harmless at runtime (`dict.get(None)` just misses) but the exact thing
  `make lint-mypy` was failing on, since 2026-08-24's BUG-0040 fix above.
- Added: `mypy.ini` -- `make lint-mypy` previously ran with no config
  (`--ignore-missing-imports --exclude submodules` inline in the Makefile), so it
  accepted untyped functions and unannotated returns. Now enforces
  `disallow_untyped_defs`/`disallow_incomplete_defs` plus six previously-free
  strictness flags (`check_untyped_defs`, `warn_redundant_casts`,
  `warn_unused_ignores`, `warn_unreachable`, `strict_equality`,
  `no_implicit_reexport`); added the ~15 missing annotations this required across
  `serve.py`, `lib/cache.py`, `lib/yaml_config.py`, `lib/validation.py`,
  `lib/reporting.py`, `lib/vendor.py`, `stage-vendor.py`, and
  `rpm-dir-prefixes-convert.py`. `disallow_any_generics` and `warn_return_any` stay
  off for now, each commented with the `docs/todo.md` entry (TODO-0079/-0081) that
  turns it on.
- Fixed: `mpvpaper`/`waypaper`'s `version:` in `packages.yaml` were unquoted YAML
  scalars (`1.9`, `2.8`) that loaded as Python `float`, not `str`. Harmless today
  only because ~15 call sites already defensively wrap `str(meta["version"])`;
  `gen-spec.py`'s two GitHub-release-cache/bundled-dep-tarball sites didn't, and a
  two-component version whose minor reaches `10` would parse as the wrong float
  (`1.10` -> `1.1`). Quoted both values and added the missing `str()` calls.
- Changed: 16 inline `os.environ.get(X, "").lower() == "true"` boolean-env parses
  (`PROCEED_BUILD`, `SKIP_MOCK`, `SKIP_COPR`, `SYNCHRONOUS_COPR_BUILD`,
  `REQUIRE_CHROOT_COVERAGE`, `FORCE_CHECKSUM`) across `stage-srpm.py`,
  `stage-vendor.py`, `stage-copr.py`, `stage-validate.py`, `stage-spec.py`,
  `stage-mock.py`, `full-cycle.py`, `refresh-checksums.py` now go through
  `lib.config.env_flag()` (already used by 4 other call sites, and written
  specifically for this) instead of matching only the literal `true`.
  `make stage-mock PACKAGE=X PROCEED_BUILD=1` previously ran in non-proceed mode
  with no error, silently dropping the operator's opt-in.
- Fixed: `run_cmd()` (`lib/subprocess_utils.py`) no longer raises `ValueError` from
  inside a helper documented to return `(ok, stdout, stderr)`, when `CMD_TIMEOUT`
  is set to a non-numeric value (or inherited empty from `.env`). Falls back to the
  3600s default with a stderr warning instead.

## 2026-08-23

- Fixed: `update_package_releases()` (`lib/yaml_utils.py`) now writes `release:`
  values through yaml load/dump like the rest of the module instead of a
  `MULTILINE|DOTALL` regex substitution that could rewrite the *next* package's
  release (or silently no-op) when a package block didn't match the expected
  two-space `release:` shape. A release update targeting a package absent from
  packages.yaml now raises instead of being reported as written. Fixes #BUG-0011.
- Fixed: `rpm-dir-prefixes-convert.py`'s `apply_replacements()` now mutates the parsed
  `files:` lists in place instead of doing a file-global raw-text `str.replace`/regex
  substitution -- the old version could rewrite a matching path anywhere else in
  packages.yaml (`requires:`, `build.install`, a `description`, ...), never re-parsed
  the result before writing, and emitted double quotes into a file where every
  `files:` entry is single-quoted. This script runs unattended every night via `make
  update-daily` -> `fmt` -> `normalize-paths`. Added `tests/test_rpm_dir_prefixes_convert.py`
  (previously untested, docs/todo.md #TODO-0041).
- Added: `lib.yaml_utils.write_yaml_file()`, a shared writer that preserves a YAML
  file's existing `---` document start (previously every packages.yaml/groups.yaml
  writer using `dump_yaml_pretty()`/`yaml_config.DEFAULT` silently dropped it, since
  that config always sets `explicit_start=False`). Routed `update_package_releases()`,
  `write_yaml_preserving_comments()`, `delete-package.py`, `set-package-release.py`,
  `scaffold-package.py`, and `lib.source_lock.save_lock()` through it.

## 2026-08-19

- Fixed: `eww`, `satty`, `ironbar`, and `cliphist` (`packages.yaml`) each
  extracted their vendor tarball twice -- an explicit `tar xf %{SOURCE1}` in
  `build.prep` on top of `stage-spec.py`'s auto-inject. Dropped the redundant
  explicit line for all four (kept `eww`'s `cargo update -p time@0.3.34
  --offline` prep step); regenerated `packages/{eww,satty,ironbar}/*.spec` to
  match (`cliphist.spec` was already correct once BUG-0029's build-system gate
  below was widened, so it needed no regen). `hyprland-per-window-layout` and
  `aylurs-gtk-shell` were already correct and needed no change. Fixes
  #BUG-0028.
- Fixed: `stage-vendor.py`'s `run_for_package` spec-stage gate no longer lumps a
  missing spec row (never run) together with a failed spec run under one
  misleading `reason="spec failed"`, and now also special-cases a `skipped` spec
  state -- previously that fell through and vendored anyway. Reasons are now
  `"spec not run"` / `"spec failed"` / `"spec skipped"` respectively. Fixes
  #BUG-0027.
- Fixed: `go mod vendor` (`vendor_golang.py`), `cargo vendor`, and `cargo update -p`
  (`vendor_rust.py`) now run with a timeout, reading `CMD_TIMEOUT` (default 3600s,
  same default as `lib.subprocess_utils.run_cmd`) and raising `VendorError` instead
  of letting `subprocess.TimeoutExpired` propagate uncaught. Previously they ran
  with no timeout at all, so a hung vendor invocation blocked `update-daily`
  indefinitely. Fixes #BUG-0024.
- Fixed: `Makefile`'s `stage-spec`, `stage-vendor`, `stage-srpm`, and `stage-copr`
  targets now forward `MOCK_CHROOT` into the container (previously only `stage-mock`
  did), and `stage-vendor` now forwards `SKIP_PACKAGES` too. Without this, a
  `MOCK_CHROOT` override resolved a different `target` on those stages than on
  `stage-mock`/`full-cycle`, splitting build-report.db rows across targets. Fixes
  #BUG-0019.
- Fixed: `stage-spec.py`'s vendor-tarball extraction (`generate_spec()`) no
  longer assumes the vendor archive sits at `archives[1]`, no longer
  substring-matches on `"vendor"` (now requires an exact `-vendor.tar.gz`
  suffix), and is no longer cargo-only -- it now scans `source.archives` for
  any build system and extracts from the matched entry's actual `%{SOURCEn}`
  index (skipping the inject if a package's own `prep` already references
  that source itself, e.g. `aylurs-gtk-shell`'s `pushd cli` extraction). Fixes
  the case that let a Go package with a two-source layout (`cliphist`)
  silently get no extraction, on top of the existing reordering hazard. Fixes
  #BUG-0029.
- Fixed: `scripts/lib/vendor_golang.py` and `scripts/lib/vendor_rust.py` no
  longer hand-roll their own `CMD_TIMEOUT` lookup, `TimeoutExpired` catch, and
  log-append block around each subprocess call -- they now go through
  `lib.subprocess_utils.run_cmd` (extended with a `cwd` parameter), the same
  helper every other stage script already uses.

## 2026-08-18

- Changed: groomed `docs/bugs.md`/`docs/todo.md` -- re-verified every entry against
  current code, added a `[P#/D#]` priority/difficulty marker to each (documented in
  both file headers, plus a next-free-ID line to stop future re-allocation), and
  reformatted entry IDs from `**BUG-0000**` to `#BUG-0000` to match how they're
  already written in commit subjects. Replaced the `## Next` section (which only
  restated body entries and had silently become the source of BUG-0018's duplicate
  ID) with a `## Unsorted` intake section for genuinely under-investigated items;
  moved TODO-0010/0012/0013 there since none had a stated problem or acceptance
  criterion. Deleted 3 entries found already resolved: BUG-0004 (dependency-triggered
  release bumps work correctly, per `lib/cache.py`/`lib/yaml_utils.py`), TODO-0053
  (mixed cargo+golang `build_requires` is now a hard `VendorError`, not a silent
  Rust-preference), and the `## Next`-only half of TODO-0072 (`preflight_autoheal()`
  already auto-inits submodules and auto-refreshes checksums, `full-cycle.py:88-115`).
  Renumbered the surviving TODO-0072 (build logs copied instead of bind-mounted) to
  TODO-0074 to resolve the ID collision, added TODO-0075 (split out of TODO-0068's
  concurrency half) and TODO-0076 (gen-spec staleness, split out of TODO-0073), and
  filed BUG-0046 (`full-cycle-matrix` drops `SKIP_PACKAGES`/`FORCE_REBUILD`). Corrected
  stale figures across a dozen entries (line counts, package counts, git-call counts)
  and repointed 5 dangling `docs/bugs.md BUG-0025`/`BUG-0041` references (both fixed
  and deleted from bugs.md already) to `docs/CHANGELOG.md` instead, in
  `refresh-checksums.py`, `lib/validation.py`, `lib/pipeline.py`, `Makefile`, and
  `docs/packaging.md`. No production code changed.
- Fixed: `tests/integration/test_make_targets.py`'s `TestCoprGatedByMockFailure`,
  `TestForceRebuildOverridesProceed`, and `TestCoprGatedByChrootCoverage` classes
  went stale after BUG-0045's `vendor_decision()` started calling the real
  `stage-vendor.run_for_package()` for packages with no vendor stage -- these
  tests' fixture `meta` dicts are empty, so `run_for_package()`'s
  `meta["version"]` lookup raised `KeyError`. Extracted the three tests' near-
  identical `patch.object` stacks into a shared `_patched_pipeline()` context
  manager and added `stage-vendor` to it, alongside the other already-patched
  stages. While consolidating, also fixed `TestCoprGatedByMockFailure._run`
  making a live Copr API call and reading the developer's real
  `REQUIRE_CHROOT_COVERAGE` env var (neither `print_chroot_coverage` nor
  `os.environ` were patched there, unlike in `TestCoprGatedByChrootCoverage`).
  No production code changed.
- Removed: `scripts/set-package-release.py`'s `sys.path.insert(0,
  str(Path(__file__).parent))` -- redundant, since Python already puts the
  running script's own directory at `sys.path[0]` when invoked as `python3
  scripts/set-package-release.py`, same as every other top-level script that
  imports from `lib/` without this line (TODO-0047).
- Removed: the Python <3.12 manual-validation fallback in
  `lib/vendor.py:_extract()`'s `except TypeError` branch. The container only
  ever runs Fedora 43/44/rawhide, all of which ship Python >=3.12, so
  `tarfile.extractall(..., filter="data")` never raises `TypeError` here --
  the fallback was unreachable (TODO-0054).
- Removed: `docs/todo.md` TODO-0059 (`SOURCES_DIR.mkdir()` only in
  `stage-vendor.py:main()`) -- already fixed 2026-08-12, stale entry, no code
  change.
- Fixed: `.env` `LOG_LEVEL=""`/`CMD_TIMEOUT=""` are now quote-stripped by the
  Makefile like `FEDORA_VERSION`/`COPR_REPO`/`PACKAGE`/`SKIP_PACKAGES` already
  were. Previously `LOG_LEVEL=""` survived as the literal two-character string
  `""`, so make's `$(if $(LOG_LEVEL),...)` treated it as non-empty and injected
  `-e LOG_LEVEL=""` into the container instead of leaving it unset (BUG-0008).
  `CMD_TIMEOUT=""` had the same root cause but crashed every subprocess call,
  since `run_cmd()` does `int(os.environ.get("CMD_TIMEOUT", 3600))` on the
  empty string (BUG-0042).
- Fixed: `make clean-localrepo` now depends on `check-image`. It runs
  `$(CONTAINER_PYTHON) scripts/db-artifacts.py` directly with no image check
  in its prereq chain, and that call is guarded by `... || true`, so a missing
  container image previously printed a raw podman error and silently
  continued instead of failing with the "run make container-build" hint every
  other container-backed target gives (BUG-0007; `save-last-build` and
  `clean` from the same report turned out not to need this -- `save-last-build`
  never touches the container, and `clean` already gets `check-image`
  transitively through its `clean-logs` prerequisite).
- Removed: `docs/bugs.md` BUG-0005 (`add-submodule` PACKAGE check) was already
  fixed in the code (Makefile, since 2026-04-05) -- stale entry, no code change.
- Fixed: `save_release_cache` now evicts entries older than `CACHE_TTL` (7
  days) on every write instead of only TTL-gating reads. Previously
  `cache/github-releases.json` kept one entry per `(url, version)` ever seen
  for every package, so the file grew unbounded across version bumps
  (BUG-0003).
- Fixed: dev tooling (ruff/mypy/flake8/yamllint/rpmlint/pytest-cov) is now installed by a
  dedicated `make install-dev` target that every lint/fmt/coverage target depends on, instead of
  as a side effect of `lint-flake` -- `make lint` on a fresh `.venv` no longer fails at
  `lint-ruff` with "ruff: command not found" (BUG-0032). The CI workaround step that installed
  `requirements-dev.txt` up front is removed.
- Fixed: the vendor stage no longer reports `reason=cached` for packages that
  have no vendor stage at all (not Go/Rust, or `fedora:<ver>: skip`).
  `full-cycle.py` used to treat any `state="skipped"` vendor row as a cache
  hit and overwrite its real `reason` (`not-vendored`, `config: skip`, `spec
  failed`) with `cached`; the summary table and `docs/full-report.md` then
  showed a build step that never ran as if it had been skipped-because-
  unchanged. Vendor's applicability is now decided from `packages.yaml`
  (`lib.vendor.needs_vendoring`, `lib.pipeline.vendor_decision`) every run
  instead of trusted from a stale DB row -- as a side effect, a vendor row
  stuck at `state="skipped", reason="spec failed"` (BUG-0020) is no longer
  permanent once the spec is fixed. The summary table and
  `docs/full-report.md` render this case as `n/a` instead of `cached`/
  `Skipped`. See `docs/bugs.md` (BUG-0045 removed, BUG-0020 narrowed).
- Changed: retired BUG-0020's remaining "`full-cycle.py` never calls
  `prepare_stage()` for the vendor stage" half after verifying it is a
  non-bug, not a fix. `prepare_stage()` is the `make stage-<x>` standalone
  entry-point helper; `full-cycle.py` deliberately calls it for no stage,
  not just vendor. Its filtering is already superseded by
  `full-cycle.py`'s own `prepare_packages()` (which additionally
  topo-sorts and expands transitive deps), and its `clear_stage()` call
  deletes the `stage_results` row -- including `hashes_json` -- that
  `lib.pipeline.is_cached()` depends on; wiring it into full-cycle would
  turn every stage into a permanent cache miss and force a full rebuild of
  all packages on every `update-daily` run. See `docs/operations.md` and
  the `prepare_stage()`/`run_build_pipeline()` docstrings for the durable
  explanation.

## 2026-08-12

- Changed: stage/pipeline logging replaced with single-line, RFC3339-timestamped,
  tab-separated `key=value` events (`lib.reporting.event()`), always carrying
  `target=` so concurrent-target output is unambiguous; `state=` and `stage=` are
  each colorized (state by RUN/OK/FAIL/SKIP/CHECK, stage with one hue per pipeline
  stage for fast visual filtering) only on a tty (`NO_COLOR` respected). Dropped
  the multi-line `=== stage ===` banners and per-package `\n  <pkg>:` headers that
  broke on narrow terminals. See `docs/operations.md` "Stage event lines".
- Fixed: `CONTAINER_RUN` (Makefile) now passes `-t` to `podman`/`docker run` when
  make's own stdout is a terminal (`MAKE_TERMOUT`, not the broken
  `$(shell test -t 1 ...)` pattern -- `$(shell)` always pipes its subshell's
  stdout to capture the return value, so that check was always false) and
  forwards `NO_COLOR` into the container. Without `-t`, the container's stdout
  was always a plain pipe, so `lib.reporting`'s colorized event lines were
  invisible to `isatty()` even when `make full-cycle` was run interactively.
- Fixed: `stage-vendor.run_for_package()` now creates `SOURCES_DIR`
  (`/root/rpmbuild/SOURCES`) itself instead of relying on `main()` to have done
  it -- `full-cycle.py`'s per-package pipeline calls `run_for_package()`
  directly and never goes through `main()`, so a fresh `rpmbuild-<version>`
  volume (no prior `make stage-vendor` run) crashed on the first Go/Rust
  package's vendor stage with `FileNotFoundError` writing the vendor tarball.

## 2026-08-11

- Added: `make submodules-update` (safe: `git submodule sync`+`update --init --recursive --force`
  to the commit git already has recorded), `make submodules-purge` (destructive: `git submodule
  deinit -f --all` + wipe `.git/modules/submodules`, confirmation required), and `make
  sync-hard-reset` (destructive: hard-resets the repo and all submodules to `origin/<branch>`,
  stashing/reapplying uncommitted main-repo changes around it, confirmation required) — for
  resolving submodule conflicts without hand-rolling the git incantation each time.
- Changed: `local-repo/` is now scoped per chroot (`local-repo/<target>/`) instead of one
  shared directory for every Fedora version, so an RPM built for one Fedora version can no
  longer be served into a different version's buildroot (the `aquamarine`/`libdisplay-info`
  soname mismatch that prompted this). One-time cost: every package's `mock` stage rebuilds
  once per target. Old flat RPMs under `local-repo/` are no longer served; `stage-mock` warns
  if it finds any (`rm -rf local-repo/*.rpm local-repo/repodata` to clean up).
- Added: `scripts/lib/repo_preflight.py` — `stage-mock` now checks each package's local deps
  are present in `local-repo/<target>/` (right dist tag) *before* spawning mock, failing fast
  with an actionable message instead of a multi-minute dnf5 resolution failure. Override with
  `SKIP_REPO_PREFLIGHT=1`.
- Added: `db-artifacts.py --forget-repo <target>`, used by the fixed `clean-localrepo` below.
- Fixed: `make clean-localrepo` was purging the unused `local-repo-<ver>` podman volume instead
  of the directory mock actually reads (`--addrepo` always pointed at the bind-mounted
  `local-repo/`, not the volume) — the remediation this doc and `_analyze_mock_root_log`
  recommended was a no-op. Now deletes `local-repo/<target>/` and its ledger rows.
- Fixed: `save-last-build` copied that same unused volume onto the live `local-repo/`; its
  `build-report.db` snapshot now goes to `logs/build-report.db.last`.
- Fixed: `prune_local_repo()` could let an fc43 build beat and delete a correct fc44 build of
  the same package by EVR alone — per-chroot directories make that comparison correct.
- Removed: the `local-repo-<ver>` podman volume and `mock-local-repo.conf` (dead — nothing
  `include()`d it). A guarded legacy `volume rm` stays in `container-volume-clean` for one cycle.
- Added: `_analyze_mock_root_log` now detects unsatisfiable buildroot transactions ("Failed to
  resolve the transaction" / "nothing provides Z") and, for a stale `local-repo` package,
  recommends rebuilding it for the current chroot before falling back to
  `clean-mock-cache`/`clean-localrepo`. Previously this class of failure produced no actionable
  output at all.

## 2026-08-09

- Added: mock's buildroot cache (`/var/cache/mock`, `/var/lib/mock`) now persists across
  `--rm` containers via the new `mock-cache-<ver>`/`mock-root-<ver>` volumes, so
  `make full-cycle`/nightly `update-daily` no longer re-bootstrap every chroot from scratch
  (docs/todo.md TODO-0014, resolved). `make clean-mock-cache` (also run by
  `clean-localrepo`/`clean-all`/`container-volume-clean`) drops them if a stale local-repo
  poisons the persisted dnf cache. `stage-mock.py` now clears `/var/lib/mock/<chroot>/result`
  before each build so a crash mid-run can't leak a prior package's RPMs into the next one.
- Changed: `make sources` and `make stage-log-analyze` each now run one container for the
  whole `PACKAGE` list instead of one container per package (`scripts/pkg-log-analysis.py`
  gained a multi-package CLI). `make readme` renders all three templates
  (README.md/docs/README.copr.md/docs/full-report.md) from one container and one Copr poll
  instead of three (docs/todo.md TODO-0067, resolved) -- `scripts/gen-report.py`'s
  `--format`/`--output` are now repeatable, paired positionally.

- Added: `FORCE_REBUILD=1` for `make full-cycle`/`make stage-show-plan` -- ignores the cache
  and re-runs every stage (spec through copr) for the requested `PACKAGE`(s), or all packages
  if `PACKAGE` is unset. Scoped to the packages named explicitly; transitive deps pulled into
  the run still respect the cache. Takes precedence over `PROCEED_BUILD` for the packages it
  applies to. See `docs/operations.md` "Build cache and forcing a re-run".
- Removed: the `FORCE_MOCK` Makefile flag (docs/bugs.md BUG-0009 -- it was passed into the
  container but nothing ever read it); replaced by the real `FORCE_REBUILD` above.
- Added: `scripts/lib/log_analysis.py` now recognizes gmake's `No rule to make target 'X',
  needed by 'Y'` error (e.g. quickshell's `dbus_objectmanager.cpp` missing from
  `redhat-linux-build`) instead of falling through to the generic `%build` failure message.
- screeninfo and quickshell packages are fixed for Fedora 43

## 2026-08-06

- Added: `lib/log_analysis.py` now recognizes CMake `FetchContent`/`ExternalProject`
  fallbacks in mock build logs (`error: could not find git for clone of <dep>`), which
  previously surfaced only as a generic "Bad exit status" line. The new rule names the
  dependency, the version CMake wanted, and the `CMakeLists.txt` line that triggered it,
  and suggests providing packages via `dnf repoquery`.
- Added: `glaze-v7` compat package -- glaze 7.9.1 installed to versioned paths
  (`%{_includedir}/glaze-v7`, `%{_datadir}/glaze-v7`) so it coexists with `glaze` 8.x.
  Hyprland v0.56.2 pins `find_package(glaze 7...<8)` and was silently falling back to
  a network `FetchContent` that cannot work in mock; it now builds against `glaze-v7-devel`.
- Fixed: `glaze-v7`'s `%cmake` override passed a relative path to `-Dglaze_INSTALL_CMAKEDIR`
  (`share/glaze-v7`). CMake absolutizes an uninitialized `CACHE PATH` variable set via `-D`
  against the command's working directory, not `CMAKE_INSTALL_PREFIX` -- unlike the
  GNUInstallDirs vars (`CMAKE_INSTALL_INCLUDEDIR`), which stay prefix-relative. The `.cmake`
  package config files (`FindAsio.cmake`, `glazeConfig.cmake`, ...) installed into the source
  tree under `BUILD/` instead of `BUILDROOT`, so `%{_datadir}/glaze-v7/*.cmake` in `%files`
  matched nothing and rpmbuild reported "Installed (but unpackaged) file(s) found". Now passes
  an absolute path (`%{_datadir}/glaze-v7`), confirmed with a local cmake configure/build/install
  against the upstream v7.9.1 and v8.0.0 tags. See `docs/packaging.md` "Compat packages".

## 2026-08-05

- Added: `build.system: python` now works. `lib/build_systems.py` pointed it at the
  nonexistent `%pyproject_build` macro; it's now `%pyproject_wheel`/`%pyproject_install`. A new
  `build.save_files: <module>` key drives `%pyproject_save_files -l -a <module>` and
  `templates/spec.j2` renders `%files -f %{pyproject_files}` when it's set (`-a`/auto is
  required -- without it, entry-point scripts under `%{_bindir}` and `data_files` like
  `.desktop`/icon/man entries are silently dropped from the package). Both spec generators
  (`stage-spec.py`, `gen-spec.py`) wire this through.
- Added: `scaffold-package.py`/`lib/detection.py` now detect Python projects
  (`pyproject.toml`/`setup.py`) instead of falling through to `build.system: FIXME`. Reads
  PEP 621 `[project]` or Poetry `[tool.poetry]` metadata (summary, dist name, build-backend)
  with a `setup.py` regex fallback, guesses the top-level importable module name for
  `build.save_files`, and maps the PEP 517 backend (`setuptools.build_meta`,
  `poetry.core.masonry.api`, `hatchling.build`, `flit_core.buildapi`, `pdm.backend`) to the
  right `BuildRequires`. Scaffolded Python packages now also default to
  `rpm.buildarch: noarch` and `rpm.no_debug_package: true`.

## 2026-08-03

- Fixed: vendoring (`make stage-vendor`) can no longer write inside `submodules/`. The
  `hyprland-per-window-layout` submodule-vendor path (the only package that used it) is deleted;
  the package now points `source.archives[0]` at a real tag-archive URL, hash-pinned in
  `sources.lock.yaml` like every other package. Go and Rust vendoring now share one
  download/verify/extract path in `lib/vendor.py`, dispatching to `lib/vendor_golang.py`/
  `lib/vendor_rust.py` from a scratch tmpdir; a package listing both `golang` and `cargo` in
  `build_requires` now fails loudly instead of silently taking the Rust path. `lib/validation.py`
  now rejects any package whose `source.archives[0]` doesn't resolve to an `https://` URL --
  closes docs/todo.md TODO-0001/TODO-0003/TODO-0044/TODO-0055/TODO-0060 and docs/bugs.md
  BUG-0021/BUG-0022/BUG-0026
- Added: `stage-vendor.py` now checks a content-addressed vendor tarball store
  (`lib/vendor_store.py`, `.cache/vendor/<pkg>/<input-hash>/`) before running `cargo
  vendor`/`go mod vendor`, keyed by the same `lib.cache.compute_input_hashes` every other
  stage's cache uses. Unlike the per-`FEDORA_VERSION` `~/rpmbuild/SOURCES` volume, this store is
  shared across every target, so `make full-cycle-matrix` vendors a given tree once instead of
  once per Fedora version. Store entries are recorded in the `artifacts` table under
  `realm="vendor-store"` and reclaimed by `make db-prune` -- closes docs/todo.md
  TODO-0002/TODO-0006 and docs/bugs.md BUG-0023
- Added: `make stage-mock` now runs mock with `rpmbuild_networking=False`/`use_host_resolv=False`,
  reproducing COPR's offline `%build` step locally, so an incomplete vendor tree fails locally
  instead of only on COPR -- closes docs/todo.md TODO-0004
- Added: `stage-vendor` now fails a Rust package's vendor stage if `cargo vendor` produces any
  crate without a registry checksum (`.cargo-checksum.json`'s `"package": null`, the signature of
  a git/path source unresolvable offline) instead of reporting success and letting the build fail
  two stages later -- closes docs/todo.md TODO-0005
- Added: `lib/toolchain.py` compares a vendored package's `go.mod` `toolchain` directive or
  `Cargo.toml` `rust-version` (vendoring runs against the container's own `go`/`cargo`) against
  what the target Fedora release's repos would install into the mock chroot, via `dnf repoquery`,
  and fails the vendor stage loud on skew instead of letting the chroot build fail offline later
  -- closes docs/todo.md TODO-0007

## 2026-08-02

- Fixed: `update-daily` now runs `make stage-log-analyze` after `readme` (tolerant of its
  non-zero "issues found" exit code) so that night's mock and Copr build failures get analyzed
  while the logs still exist. Previously nothing called `stage-log-analyze` from the nightly
  flow, and the next night's `full-cycle.py:main()` `rmtree`s `logs/build/<pkg>` before building
  -- destroying unread failure evidence, including async Copr failures only discovered by that
  same `readme` step's Copr poll (`lib.copr.poll_copr_status`) -- closes BUG-0041
- Added: `sources.lock.yaml` (committed) pins a sha256 for every remote file a package's
  `source.archives`/`source.bundled_deps` download (`lib/source_lock.py`). `make
  refresh-checksums` (new target, also run automatically by `update-daily` after
  `update-versions`) is the only thing that writes it; `stage-srpm.py` now verifies every
  downloaded source against it between `spectool -g` and `rpmbuild -bs`, and the Go/Rust vendor
  download path (`lib/vendor.py:verify_download`, called from both `lib/vendor.py`'s Go branch and
  `lib/vendor_rust.py`'s download branch) does the same for the tarball it fetches directly --
  both fail closed (no entry, or a hash that no longer matches) instead of silently packing
  whatever was downloaded into the SRPM pushed to Copr. `make check-checksums` (also run by
  `make sources`) verifies without downloading or writing. `make stage-validate` now warns (not
  errors, so a fresh checkout isn't blocked) when a package's remote sources have no lock entry
  yet. TOFU trust model, no signature verification (tracked as a TODO) -- closes BUG-0025
- Changed: `make update-daily` no longer runs the full `pre-commit` gate (test+lint+fmt) before
  building -- just the new `validate-packages` target (packages.yaml/.gitmodules structure
  checks, extracted from `pre-commit`'s first line so both can reuse it) plus `fmt`. `scripts/`
  lint/test health is already CI's job on every push/PR; an unrelated regression there no longer
  blocks a nightly Copr publish (closes TODO-0064). Also: a package build failure inside
  `full-cycle` no longer aborts the rest of the run -- `readme`/`copr-description`/`git commit`
  still happen (so the night's version bumps aren't lost), and `update-daily` reports the
  failure and exits non-zero only at the end, after everything else has run (closes TODO-0061)
- Changed: `PACKAGE` env var semantics on the Makefile, closing TODO-0029 -- `gather-requires`
  (the one target where it was a filesystem path to a built `.rpm`, not a packages.yaml key)
  now takes `RPM=` instead; `list-tags`/`scaffold-package`/`add-submodule`/`delete-package`
  (single-package-only targets) now reject a comma-separated `PACKAGE` with a clear error
  instead of a confusing downstream one (`KeyError`, wrong path, silent no-op); `sources`/
  `stage-log-analyze` now accept the same comma-separated-list shape every other multi-package
  target already does, instead of silently treating `PACKAGE=a,b` as one bogus package name
- Added: `make full-cycle-matrix` builds every `MATRIX_VERSIONS` (default: all `SUPPORTED`)
  Fedora version's x86_64 chroot locally via mock, then submits to Copr once; and
  `stage-copr`/`full-cycle` now print a per-chroot local-mock coverage table (verified/failed/
  unbuilt/not-locally-verifiable) before every Copr submission, warning by default and blocking
  under `REQUIRE_CHROOT_COVERAGE=true`. Narrows BUG-0018 to its aarch64 residual (blocked on
  TODO-0024) -- x86_64 chroot-specific failures are now catchable before submission
- Fixed: `update-versions.py:pull_submodule()` no longer force-moves every submodule to upstream
  HEAD regardless of `auto_update.release_type` -- a `pinned-tag`/`pinned-commit`/`pinned-version`
  package now gets its submodule checked out *detached* at `refs/tags/<tag>` /
  `source.commit.full` / `refs/tags/v<version>` (falling back to the bare `<version>` tag for
  upstreams that don't use a `v` prefix), and an unresolvable pin leaves the checkout exactly
  where it is instead of falling back to branch HEAD, so `update-daily`'s `git add submodules/`
  stops committing a moved gitlink under a package the operator believes is frozen (closes
  BUG-0033 -- the `update-versions.py:pull_submodule()` one, not the unrelated `.git`-suffix entry
  reusing that ID lower in this file). A pin also now wins over a moving sibling sharing the same
  submodule url, safe because version resolution no longer reads the working tree:
  `lib/gitmodules.py:get_submodule_commit_with_base()` takes a `ref`, so `latest-commit`/default
  packages resolve `origin/<branch>` instead of whatever HEAD happens to be, and
  `lib/cache.py:_source_commit()` reads `source.commit.full` from packages.yaml -- the hash the
  build actually downloads via `%{commit}` -- instead of the live checkout. `git fetch` now passes
  `--tags` so a pinned tag resolves even when unreachable from the tracked branch
- Fixed: `lib/cache.py:_source_commit()` now returns `None` for every package except the 3 whose
  `auto_update.release_type` is `latest-commit`/`pinned-commit` (the ones that actually build from
  `%{url}/archive/%{commit}.tar.gz`) instead of hashing the submodule's live checkout for all 45 --
  a nightly submodule pull no longer flips every release package's cache and forces an
  unchanged-version rebuild+resubmit (closes BUG-0034, BUG-0001)
- Fixed: `lib/yaml_utils.py:update_package_releases()` now decides "needs a release bump" from the
  same full input-hash set (`source_commit`/`templates`/`package_config`/`dependencies`/`patches`)
  that `lib/pipeline.py:is_cached()` uses to decide "needs an actual rebuild", instead of the
  package's own content hash alone -- a rebuild triggered by an edited template/patch or a
  dependency's config change now always gets a release bump, so a different RPM never ships under
  an NVR already on Copr (closes BUG-0035)
- Fixed: `make update-daily` no longer fails on a no-op night (nothing staged skips the commit
  instead of `git commit`'s nonzero exit aborting the target), and `PUSH=1` now rebases onto
  `origin/main` before pushing so it doesn't collide with `publish-readme.yml`'s own `[skip ci]`
  push to `main` (closes BUG-0037, BUG-0038)
- Added: this changelog and its ruleset (see docs/CONTRIBUTING.md)
- Added: CI (GitHub Actions) runs lint+test on every push/PR, natively via `NO_CONTAINER=1`
- Changed: `make update-daily` now runs the `pre-commit` quality gate (validate+test+lint+fmt)
  before building, instead of `fmt` alone; merged five separate `$(MAKE)` sub-processes into one
  (closes TODO-0034); narrowed its `git add` to generated paths only (no longer stages
  `templates/`/`blog/`); added `PUSH=1` to push after committing
- Changed: moved `CONTRIBUTING.md` and `CHANGELOG.md` to `docs/`; split `CONTRIBUTING.md` into
  `docs/CONTRIBUTING.md` (contributor onboarding), `docs/operations.md` (maintainer runbook),
  and `docs/packaging.md` (`packages.yaml` schema reference); folded `docs/features/*.md` into
  `docs/FRD.md`
- Removed: dead `docs/build-report.html` (nothing generated or referenced it)
- Fixed: Makefile help text and moved/rewritten CONTRIBUTING both called Rust vendoring
  "ABANDONED"/"Go packages only", though `vendor_rust.py` is live for 2 packages (closes
  TODO-0051)
- Changed: `docs/bugs.md`/`docs/todo.md` got a scope rule, a `## Next` section, and an
  ID-reuse rule; deleted 4 entries that verbatim-duplicated the other file (TODO-0061/0062 vs.
  BUG-0028/0029) and TODO-0034/TODO-0051 (both fixed above)
- Fixed: `requirements.txt`/`requirements-dev.txt` now pin `~=X.Y.Z` (PEP 440 compatible-release:
  patch upgrades allowed, minor/major blocked) instead of open-ended `>=` floors. Found while
  wiring CI: the repo has no ruff config, so its lint behavior rides ruff's default rule set
  with nothing pinning it - `ruff==0.15.4` passes scripts/ clean, `ruff==0.16.1` (satisfies the
  old `>=0.15.4`) flags 124 errors on the exact same code (new default-enabled rules incl.
  SIM118/BLE001/N999/EXE001). A plain `make setup-venv` + `make lint` on a fresh clone was one
  `pip install` away from failing on unrelated code, independent of any PR's actual changes
- Removed: Fedora 42 (EOL) from `SUPPORTED` in the Makefile, the `.env.example` comment, and a
  stray test name - the maintainer had already announced dropping it back in `blog/NEWS.md`'s
  2026-03-10 entry, but the Makefile's version list was never actually updated to match
- Changed: merged 8 separate `blog/*.md` posts into one microblog-style `blog/NEWS.md`
  README's News section now shows the most recent entries (default 8,
  configurable via `repo.yaml` `documents.news_limit`) instead of just the latest one -
  `get_recent_news()` (`lib/readme_content.py`, replaces `get_latest_blog()`) extracts
  `## `-delimited sections instead of glob-sorting filenames - closes TODO-0063 (mixed
  per-day/per-month filenames had a latent lexicographic-sort collision) since there's only one
  file now
- Added: `repo.yaml` `documents.sections` - per-block visibility toggle (`news`/`docs`/
  `support`/`license`/`authors`/`maintainers`/`contributors`/`additional_info`) for generated
  docs, defaulting to `true` when unset. `__header.j2`/`__footer.j2` gate each block on it;
  useful as an immediate workaround for BUG-0030 (`contributors: false`) without touching the
  underlying template
- Added: `scripts/gen-readme-shell.py` / `make readme-shell` - regenerates only the branding
  shell (header/footer) of `README.md`/`docs/README.copr.md` by splicing rendered
  `__header.j2`/`__footer.j2` between their existing marker comments, leaving the
  packages/build-status body untouched. Needs no `build-report.db` (gitignored, so CI has none)
  unlike `make readme`/`gen-report.py`, which derives its entire package list from DB rows and
  would render zero packages on a from-scratch checkout. Moved the now-shared
  `collect_contributors`/`get_recent_news`/`get_sections` out of `gen-report.py` into new
  `lib/readme_content.py` so both scripts use the same code
- Added: `.github/workflows/publish-readme.yml` runs `make readme-shell` on every push to
  `main` and on manual dispatch, auto-committing (`[skip ci]`) and pushing if anything changed
- Fixed: stage cache now verifies the recorded artifact is still on disk before skipping a
  stage (`lib/pipeline.py:artifacts_present()`, version-scoped against `artifacts` rows), and
  `stage-mock.py`/`stage-copr.py` refuse a recorded-but-missing SRPM instead of handing it to
  mock/copr-cli (closes BUG-0015, TODO-0016)
- Fixed: `Waybar-git`/`hyprland-plugins-git` `packages.yaml` `url` didn't exactly match their
  `.gitmodules` submodule url (a stray/missing trailing `.git`), so `update-versions.py`'s
  exact-match lookup silently skipped their `auto_update` every run; also found and fixed 5 more
  packages hitting the same class of drift (`cpptrace`, `libdwarf-code`, `eww`,
  `snappy-switcher`, `mpvpaper`) plus a `Waybar` (stable) regression this fix would otherwise
  have introduced via the shared submodule url (closes BUG-0013). Added
  `validate_submodule_url_resolution()` (`lib/validation.py`, wired into `stage-validate.py`)
  and an equivalent check in `validate-packages.py` (the pre-commit gate) so this can't recur
  silently again
- Removed: dead `scripts/validate-package-urls.py` (closes TODO-0037) -- unreferenced outside
  its own test, and its url-matching logic normalized away the exact `.git`-suffix difference
  that causes BUG-0013's failure mode, so it would not have caught it even if wired in
- Fixed: `aylurs-gtk-shell`/`cava`/`glaze`/`gtk4-layer-shell`/`Hyprshot`/`pyprland`/`cliphist`
  `url` had a stray trailing `.git` while their `source.archives` template uses `%{url}/archive/...`
  directly -> the generated Source0 404s on GitHub (confirmed live via `curl -I` before and after
  for all 7); masked until now only because each package's srpm stage was cached from before the
  `.git` was added. Dropped `.git` from both `packages.yaml` and the matching `.gitmodules`
  submodule url for all 7, keeping url-resolution and archive-fetch correctness in sync (closes
  BUG-0033). `quickshell`'s url was investigated too but left unchanged: its git host
  (`git.outfoxxed.me`, Gitea) serves an identical archive either way, confirmed by byte-identical
  `content-length` with and without `.git`
- Added: `auto_update.release_type: latest-tag` (`lib/version.py:latest_tag`) -- tracks the
  highest version-like tag (any number of dot-separated components, e.g. mpvpaper's `1.9`) with
  no commit fallback, for upstreams that don't tag strict three-component semver. `mpvpaper` had
  declared this type since it was added (#9) even though it didn't exist yet, silently falling
  through `update-versions.py`'s default path -- which resolves via the strict-semver
  `SEMVER_RE`, matching only `1.2.1` out of mpvpaper's `1.0`..`1.9` tags, so the next
  `make update-versions` would have downgraded it (closes BUG-0014)
- Fixed: an `auto_update.release_type` outside the six valid values now fails both
  `make validate-packages` and `make stage-validate` instead of silently matching no dispatch
  branch in `update-versions.py` (the other half of BUG-0014). The valid-type set, previously
  duplicated and drifting across `update-versions.py`, `lib/cache.py`, and `lib/yaml_utils.py`, is
  now one constant (`lib/version.py:RELEASE_TYPES` and friends) all four call sites import
