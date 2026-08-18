# Bugs

Automation behaving wrong today. Complexity/cleanup/features go in `docs/todo.md`
instead. GitHub issues are for reporter-facing items (someone else's bug/request);
this file is the maintainer's own log and may cite issue numbers. Entries are deleted
when fixed (the fix gets a `docs/CHANGELOG.md` bullet); IDs are never reused or
renumbered, so deletions leave gaps. Next free ID: **BUG-0047**.

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

- #BUG-0002 make sure copr stage is run only if a rebuild is really required. If prior
  status is `unknown`, it is currently treated the same as "no cache" and resubmitted
  every night -- `lib/pipeline.py:125`'s `is_cached()` requires `state == "success"`,
  so `unknown` always misses and `cache_miss_reason()` (`lib/pipeline.py:246-248`)
  literally returns `"prior-unknown"` as the resubmit reason. Closing BUG-0040 (below)
  is a precondition: as long as `poll_copr_status()` can't resolve a build past
  `unknown`, this one keeps firing on it forever [P1/D2]

- #BUG-0040 `poll_copr_status()` (`lib/copr.py:301-354`) only maps `succeeded`/`failed`
  by unanchored substring match over the whole `copr-cli status` output --
  `TERMINAL_STATES = {"success", "failed"}` (`lib/copr.py:31`). Any other terminal
  state (`canceled`, `skipped`, a stuck import) never matches, so the row stays
  `unknown` forever: re-polled every night, and (per BUG-0002) resubmitted every
  night. Already carries a `FIXME(BUG-0040)` comment at `lib/copr.py:332-335` pointing
  back here. A per-chroot listing mentioning both `succeeded` and `failed` resolves to
  whichever line the substring scan hits first, since the match is unanchored [P1/D2]

- #BUG-0011 `lib/yaml_utils.py:update_package_releases` mutates packages.yaml via
  regex string substitution on raw text instead of load/mutate/dump like the rest of
  the module -> fragile, depends on exact indentation matching. The pattern, verbatim
  at `lib/yaml_utils.py:387`: `^({pkg}:.*?^  release: )\d+(\n)` compiled with
  `MULTILINE | DOTALL` and called with no `count=` -- if a package block has no
  `release:` key at exactly two-space indent, the non-greedy `.*?` runs straight past
  the end of that block and rewrites the *next* package's release instead; a
  `release:` with a trailing comment or different indentation is a silent no-op.
  Either way `full-cycle.py:781-785` still prints `Release updates: {...}` claiming
  the write happened, so the NVR stays put and Copr rejects the resubmission as a
  duplicate. Holds together today only because all 49 packages (not 45 -- count
  re-verified 2026-08-18) happen to match the pattern exactly [P1/D2]

- #BUG-0012 `scripts/validate-packages.py` (the pre-commit gate) and
  `lib/validation.py` (used by `stage-validate`, the actual build) are two
  independent, already-diverged validators for packages.yaml/.gitmodules -> a package
  can pass pre-commit and still fail build validation, or vice versa. Concrete case
  found 2026-08-18: `validate-packages.py:109-113` checks a `depends_on` reference
  case-**sensitively**, while `lib/validation.py:129-134` resolves it through a
  case-insensitive lowercase map -- a differently-cased `depends_on` entry fails
  pre-commit but passes build validation [P2/D3]

- #BUG-0016 individual `stage-*` Makefile targets (`stage-mock`, `stage-srpm`, etc.)
  don't forward `PROCEED_BUILD` into the container's `env` the way `full-cycle` does
  -> `make stage-mock PACKAGE=X PROCEED_BUILD=true` silently drops PROCEED_BUILD, so
  `prepare_stage()` runs in its default (non-proceed) mode and clears that stage's
  rows for the packages being built (scoped to PACKAGE since the sqlite migration, no
  longer whole-stage) even though the operator explicitly tried to opt out of it
  [P2/D1]

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

- #BUG-0046 `make full-cycle-matrix` (`Makefile:529-539`) does not pass
  `SKIP_PACKAGES` or `FORCE_REBUILD` through to its per-version `full-cycle` calls, so
  a matrix run silently ignores both [P2/D1]

## stage-vendor

- #BUG-0019 `make stage-vendor` doesn't forward `MOCK_CHROOT` (nor `SKIP_PACKAGES`)
  into the container, but `stage-vendor.py:194-195,206` reads both -> with a
  `MOCK_CHROOT` override, vendor rows land under a different `target` than
  `stage-mock`/`full-cycle` use. Same problem on `stage-copr`, `stage-spec`, and
  `stage-srpm`: none of them forward `MOCK_CHROOT` either, so any override resolves a
  different `target` on each of those than on `stage-mock` [P2/D1]

- #BUG-0024 `go mod vendor` (`vendor_golang.py:57-62`), `cargo vendor`
  (`vendor_rust.py:117-122`), and `cargo update -p` (`vendor_rust.py:92-97`) all run
  with no timeout at all; the Makefile forwards `CMD_TIMEOUT` and nothing on the
  vendor path reads it -- neither module imports `lib/subprocess_utils.run_cmd`, the
  only reader of `CMD_TIMEOUT`. A hung vendor invocation blocks `update-daily`
  indefinitely [P1/D1]

- #BUG-0027 `stage-vendor.py:98-105`'s `run_for_package` records a missing spec row
  (`spec_entry is None`) with reason "spec failed" (misleading -- there was no spec
  run at all), and doesn't special-case spec `state == "skipped"` [P3/D1]

- #BUG-0028 `eww`, `satty`, and `ironbar` each extract their vendor tarball twice: an
  explicit `tar xf %{SOURCE1}` in `build.prep` in packages.yaml *and*
  `stage-spec.py`'s auto-inject for any cargo package whose `archives[1]` contains
  "vendor" -- confirmed committed twice in all three generated specs (e.g.
  `packages/eww/eww.spec:40-41`). `hyprland-per-window-layout` (also cargo, also
  vendored) is the one package configured correctly: it has no explicit `prep` line
  and relies solely on the auto-inject. Fix is to drop the redundant explicit line
  from the three affected packages' `build.prep`, not to touch the inject [P2/D1]

- #BUG-0029 that auto-inject (`stage-spec.py:158-163`) is cargo-only, positional
  (`archives[1]`), and substring-matched -> reordering sources, or a Go package with
  the same two-source layout, silently gets no extraction [P2/D1]

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
refresh-checksums -> full-cycle -> readme+copr-description -> stage-log-analyze ->
git commit -> optional push, and is documented (docs/operations.md) as the unattended
nightly job. Audited end to end 2026-08, re-verified 2026-08-18:

- #BUG-0036 Copr preflight is dropped on the `full-cycle` path: `full-cycle.py:312`
  calls `check_copr_credentials()` and throws away the returned boolean
  (`stage-copr.py:main()` exits 2 on the same check), and `validate_copr_repo()` is
  never called on this path at all -- only in `stage-copr.py:main()`. Already carries
  a `FIXME(BUG-0036)` comment pointing back here. `make update-daily
  COPR_REPO=<typo>` or an expired token runs the whole multi-hour build for 49
  packages and only fails at the very end, once per package [P1/D2]

- #BUG-0039 any package resubmitted tonight is published as `unknown`; only unchanged
  (cached) packages keep showing yesterday's resolved state (as of 2026-08-18,
  `docs/full-report.md` shows 45 `copr-success` rows and 1 `copr-unknown`, not "every
  build"). `full-cycle` submits with `--nowait` (async is the default; `update-daily`
  never sets `SYNCHRONOUS_COPR_BUILD`, though it is read at `stage-copr.py:184` and
  `full-cycle.py:153`), and `readme`+`copr-description` run seconds later -- the
  publish step is simply one poll too early for whatever was just resubmitted [P2/D3]

- #BUG-0043 no concurrency guard on a job documented as cron-driven. Nothing takes a
  lock -- repo-wide grep for `flock`/`fcntl`/pidfile/lockfile across `Makefile` and
  `scripts/` is empty. 49 packages at up to `CMD_TIMEOUT=3600s` *per command* can
  easily outrun the cron interval, and two overlapping runs write the same
  build-report.db (sqlite WAL gives it some protection), the same rpmbuild-*/mock-*
  podman volumes, the same `local-repo/<target>/` directory, the same packages.yaml,
  and the same git index -- `git pull --rebase origin main` under `PUSH=1`
  (`Makefile:564`) is the sharpest edge, two runs rebasing concurrently [P1/D2]

- #BUG-0044 the quality gate never sees the file that gets committed. Current order
  (re-verified 2026-08-18, was previously misdescribed as "pre-commit"):
  `update-versions -> validate-packages+fmt -> refresh-checksums -> full-cycle ->
  readme+copr-description -> stage-log-analyze -> git commit` (`Makefile:541-570`;
  the full `pre-commit` target with `test`+`lint` was deliberately dropped from this
  path, CHANGELOG 2026-08-02, closed TODO-0064). But `full-cycle.py:781-785` still
  calls `update_package_releases()`, which rewrites packages.yaml in place *after*
  the gate has run (via the regex of BUG-0011). The packages.yaml that lands in the
  daily commit (`Makefile:556`) is the post-regex one, which
  validate-packages.py/yamllint/format-yaml.py never inspected [P1/D2]

## Container / Makefile

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
