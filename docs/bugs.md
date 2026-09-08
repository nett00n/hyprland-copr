# Bugs

Automation behaving wrong today. Complexity/cleanup/features go in `docs/todo.md`
instead. GitHub issues are for reporter-facing items (someone else's bug/request);
this file is the maintainer's own log and may cite issue numbers. Entries are deleted
when fixed (the fix gets a `docs/CHANGELOG.md` bullet); IDs are never reused or
renumbered, so deletions leave gaps. Next free ID: **BUG-0054**.

Each entry ends with a `[P#/D#]` marker:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Unsorted

Not investigated enough to file properly: no verified root cause, no priority, no
difficulty. Move an entry into a real section below once it has all three.

(empty as of the 2026-08-18 grooming pass)

## Copr / cache

- #BUG-0012 `scripts/validate-packages.py` (the pre-commit gate) and
  `lib/validation.py` (used by `stage-validate`, the actual build) are two
  independent, already-diverged validators for packages.yaml/.gitmodules -> a package
  can pass pre-commit and still fail build validation, or vice versa. Concrete case
  found 2026-08-18: `validate-packages.py:109-113` checks a `depends_on` reference
  case-**sensitively**, while `lib/validation.py:129-134` resolves it through a
  case-insensitive lowercase map -- a differently-cased `depends_on` entry fails
  pre-commit but passes build validation [P2/D3]

- #BUG-0017 `db-artifacts.py --prune` keeps the newest artifact per (package, target,
  kind) by recorded mtime (`db-artifacts.py:92-93`), not a real NVR comparison (same
  limitation `stage-srpm.py:find_srpm` already has, `stage-srpm.py:55-59`) -> a
  rebuild that produces an older version could be kept over a newer one if it happens
  to be written later in wall-clock time [P2/D2]

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
  docs/todo.md TODO-0024), so they always report "not verifiable locally" and can
  never satisfy the coverage gate -- that residual is the only way this bug can still
  bite. `lib.copr.fetch_failed_chroot_logs` still downloads failed chroots' builder
  logs after the fact for `make stage-log-analyze`, which remains the only diagnostic
  for an aarch64-only failure [P2/D4]

- #BUG-0048 `stage-show-plan.py` (`make stage-show-plan`, and the plan preview
  `full-cycle.py` prints before running) mislabels a dependent package as `cache`
  when its dependency is actually about to rebuild this run, so the printed plan
  and the real run diverge. Concrete case 2026-08-29: `hyprutils`'s `srpm` stage
  was `FAIL` (`source verify failed`) and retried; `hyprwire`/`hyprlang`, which
  both `depends_on: [hyprutils]`, showed `mock: cache` in the plan but actually
  rebuilt `mock` (and every other stage) once the real run reached them, because
  `compute_forced_stages()`'s cascade rule (`lib/pipeline.py:87-89`: "if any
  dependency was rebuilt this run, force all stages") fired for real but the
  plan never predicted it.

  Two compounding causes in `stage-show-plan.py`:
  1. `show_plan()` (`:79`) iterates `filter_packages(all_packages_full, ...)`
     directly -- `packages.yaml`'s declared order, alphabetical in practice --
     not topologically sorted. `full-cycle.py`'s real run order comes from
     `prepare_packages()` (`:189-204`), which topo-sorts via
     `build_dep_graph()`/`topological_sort()` first, so `hyprutils` always
     builds before `hyprwire`/`hyprlang`. Without that ordering a cascade
     couldn't be predicted correctly even if computed, since a dependent would
     be evaluated before its dependency's outcome is known.
  2. `compute_forced_stages(pkg, deps, target, set(), ...)` (`:90-92`) passes a
     literal fresh `set()` for `rebuilt_packages` on every package,
     independently -- never accumulated across the loop, unlike the real run's
     one growing `rebuilt_packages` set threaded through `full-cycle.py`'s loop
     (`:323`, `.add(pkg)` at `:368` etc). The `:88` comment ("during planning,
     no packages have been rebuilt yet") describes this as a given, not
     something planned around.

  Fix needs both: topo-sort `packages_to_show` the same way `prepare_packages()`
  does, and thread a `would_rebuild: set[str]` through the loop (mirroring
  `rebuilt_packages`), adding `pkg` to it whenever any of its stages label
  `run`/`retry` [P2/D2]

## Docs / templates

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

## update-daily

`make update-daily` (Makefile) chains update-versions -> validate-packages+fmt ->
refresh-checksums -> full-cycle-matrix -> validate-packages -> readme+copr-description ->
stage-log-analyze -> git commit -> optional push, and is documented
(docs/operations.md) as the unattended nightly job. Audited end to end 2026-08,
re-verified 2026-08-18, revalidation step added 2026-08-29 (BUG-0044). `full-cycle`
was replaced by `full-cycle-matrix` in ce1d02de (2026-09-08, "run full matrix build
before pushing to copr") -- see BUG-0051 below for a defect still open, found
while investigating why three consecutive 2026-09-07/08 runs (commits d303dced,
f7363082) pushed nothing to Copr despite `update-daily` reporting success and
committing normally. The actual root cause of that incident (BUG-0053: `make -k`
plus an order-only prerequisite silently skipped every non-canonical chroot
whenever the canonical one had any package failure) and BUG-0050 (`stage-copr`'s
exit code being discarded, found in the same investigation) are both fixed --
see docs/CHANGELOG.md's 2026-09-08 section:

- #BUG-0039 any package resubmitted tonight is published as `unknown`; only unchanged
  (cached) packages keep showing yesterday's resolved state (as of 2026-08-18,
  `docs/full-report.md` shows 45 `copr-success` rows and 1 `copr-unknown`, not "every
  build"). `full-cycle` submits with `--nowait` (async is the default; `update-daily`
  never sets `SYNCHRONOUS_COPR_BUILD`, though it is read at `stage-copr.py:184` and
  `full-cycle.py:153`), and `readme`+`copr-description` run seconds later -- the
  publish step is simply one poll too early for whatever was just resubmitted [P2/D3]

- #BUG-0051 `ineligible_packages()`/`chroot_coverage()` (`lib/copr.py:189-327`) treat
  "no locally-verified mock build yet for this Copr chroot" as a per-package skip,
  not a run failure -- by design, so that one straggling package/chroot combo doesn't
  block everyone else's submission. But when a chroot has **zero** packages verified
  on it yet (a brand-new `SUPPORTED_FEDORA_VERSIONS` entry on its first night, or --
  as actually happened on 2026-09-07/08, see docs/CHANGELOG.md's 2026-09-08 entry
  fixing #BUG-0053 -- an existing chroot that a Makefile scheduling bug had kept
  from ever completing a matrix pass), every single package is "not verified on:
  <that chroot>" simultaneously, so `ineligible_packages()` blocks 100% of the run --
  and because none of those are a `run_for_package()` *failure* (they never attempt
  submission, they're filtered out before the loop, `stage-copr.py:245-258`),
  `failed` stays `False` and the script still exits 0, silently. BUG-0053's fix
  means a chroot now gets a fair attempt every night regardless of what else fails,
  so this can no longer wedge *permanently* -- but the first night any new chroot
  is added, or after any gap, still goes in cold with zero coverage and zero signal
  that that's what's blocking everything. Still needs: (a) `stage-copr.py`/
  `print_chroot_coverage()` should make an all-or-nearly-all-ineligible run loud
  (non-zero exit, or at least an unmissable summary line) even without
  `REQUIRE_CHROOT_COVERAGE=true`, since that flag currently only fires on the
  local-matrix-build-time check, not this one; (b) onboarding a new
  `SUPPORTED_FEDORA_VERSIONS` entry needs a documented "run `make
  matrix-chroot-<N>` locally at least once before the next nightly" step
  (docs/operations.md doesn't mention this) so coverage exists before the gate is
  live [P2/D2]

## Packaging metadata

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

## Container / Makefile

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

- #BUG-0010 `lib/gitmodules.py` reimplements raw git subprocess calls **15x**
  (re-counted 2026-08-18, was 8x) instead of using `lib/subprocess_utils.run_git` ->
  inconsistent timeouts (**9** of the 15 call sites have none at all: lines 68, 84,
  110, 123, 135, 160, 176, 194, 242) and error handling; `fetch_tags`
  (`lib/gitmodules.py:26-50`) catches only `subprocess.TimeoutExpired`, unlike
  `run_git` which also catches `FileNotFoundError` [P2/D3]
