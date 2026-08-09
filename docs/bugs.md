# Bugs

Automation behaving wrong today. Complexity/cleanup/features go in `docs/todo.md` instead.
GitHub issues are for reporter-facing items (someone else's bug/request); this file is the
maintainer's own log and may cite issue numbers. Entries are deleted when fixed (the fix gets a
`docs/CHANGELOG.md` bullet); IDs are never reused or renumbered, so deletions leave gaps.

## Next

- **BUG-0018** — aarch64 Copr chroots still can't be verified locally before submitting (x86_64 now can, via `make full-cycle-matrix`)

- **BUG-0002** make sure copr stage is runned only if rebuilt is really required. If status is still unknown - do not schedule new one #medium
- **BUG-0003** `lib/github.py:save_release_cache` never evicts old `(url, version)` entries from `cache/github-releases.json`, only TTL-gates read freshness -> file grows forever, one entry per version ever seen for every package #low
- **BUG-0004** does hyprpolkit increment release on rebuild, when dependency is updated #low
- **BUG-0005** `make add-submodule` doesn't check PACKAGE is set before use -> raw python KeyError instead of friendly error (unlike add-new/delete-package/set-release which do check) #low
- **BUG-0006** `make container-enter` doesn't match `$(CONTAINER_RUN)`: no `--privileged`, no `.venv`/mock-conf/copr-config mounts -> manual mock testing inside fails differently than real stages #low
- **BUG-0007** `save-last-build`, `clean`, `clean-localrepo` skip the `check-image` prereq other targets have -> raw podman/docker error instead of "run make container-build" hint #low
- **BUG-0008** `.env` `LOG_LEVEL=""` isn't quote-stripped like FEDORA_VERSION/PACKAGE/etc -> make's `$(if $(LOG_LEVEL),...)` sees non-empty `""` and injects `-e LOG_LEVEL=""` into container instead of leaving unset #low
- **BUG-0009** Makefile `full-cycle` passes `DRY_RUN` env var into the container but nothing in scripts/ reads it -> silent no-op flag, misleading (`FORCE_MOCK` was the other half of this; replaced by a real `FORCE_REBUILD` flag, see docs/operations.md) #low
- **BUG-0010** `scripts/lib/gitmodules.py` reimplements git subprocess calls 8x instead of using `lib/subprocess_utils.run_git` -> inconsistent timeouts (some unbounded) and error handling; `fetch_tags` doesn't catch `FileNotFoundError` unlike other git callers #medium
- **BUG-0011** `scripts/lib/yaml_utils.py:update_package_releases` mutates packages.yaml via regex string substitution on raw text instead of load/mutate/dump like the rest of the module -> fragile, depends on exact indentation matching. Concretely: the pattern is `^({pkg}:.*?^  release: )\d+(\n)` compiled with `MULTILINE | DOTALL` -- if a package block has no `release:` key at exactly two-space indent, the non-greedy `.*?` runs straight past the end of that block and rewrites the *next* package's release instead; a `release:` with a trailing comment or different indentation is a silent no-op. Either way `full-cycle.py` still prints `Release updates: {...}` claiming the write happened, so the NVR stays put and Copr rejects the resubmission as a duplicate. Holds together today only because all 45 packages happen to match the pattern exactly #high
- **BUG-0012** `scripts/validate-packages.py` (the pre-commit gate) and `scripts/lib/validation.py` (used by `stage-validate`, the actual build) are two independent, already-diverged validators for packages.yaml/.gitmodules -> a package can pass pre-commit and still fail build validation, or vice versa #medium
- **BUG-0016** individual `stage-*` Makefile targets (`stage-mock`, `stage-srpm`, etc.) don't forward `PROCEED_BUILD` into the container's `env` the way `full-cycle` does -> `make stage-mock PACKAGE=X PROCEED_BUILD=true` silently drops PROCEED_BUILD, so `prepare_stage()` runs in its default (non-proceed) mode and clears that stage's rows for the packages being built (scoped to PACKAGE since the sqlite migration, no longer whole-stage) even though the operator explicitly tried to opt out of it #medium
- **BUG-0017** `db-artifacts.py --prune` keeps the newest artifact per (package, target, kind) by recorded mtime, not a real NVR comparison (same limitation `stage-srpm.py:find_srpm` already has) -> a rebuild that produces an older version could be kept over a newer one if it happens to be written later in wall-clock time #medium
- **BUG-0018** local mock used to only ever build one `FEDORA_VERSION`/chroot, but a `COPR_REPO` project builds every chroot configured on Copr (fedora-43/44/rawhide x86_64/aarch64, 6 total for `nett00n/hyprland`) -> a build that passes local mock could still fail on Copr for a chroot-specific reason (the recorded case: `Hyprland-git` 0.56.0^20260730git8668a53, local mock built fedora-44 clean, Copr's fedora-43-x86_64/aarch64 failed on `std::ranges::starts_with` needing a newer libstdc++ than F43 ships). `make full-cycle-matrix` now runs the local pipeline across every `MATRIX_VERSIONS` (default: `SUPPORTED`) x86_64 chroot before a single Copr submission, and `stage-copr`/`full-cycle` print a per-chroot local-mock coverage table before submitting (warn by default, `REQUIRE_CHROOT_COVERAGE=true` blocks) -- see `lib.copr.print_chroot_coverage`/`chroot_coverage`/`get_project_chroots`. What remains: aarch64 chroots have no local build path at all (mock can't cross-build without qemu-user-static or a native runner, see docs/todo.md TODO-0024), so they always report "not verifiable locally" and can never satisfy the coverage gate -- that residual is the only way this bug can still bite. `lib.copr.fetch_failed_chroot_logs` still downloads failed chroots' builder logs after the fact for `make stage-log-analyze`, which remains the only diagnostic for an aarch64-only failure #high

## stage-vendor

- **BUG-0019** `make stage-vendor` doesn't forward `MOCK_CHROOT` (nor `SKIP_PACKAGES`) into the container, but `stage-vendor.py` reads both -> with a `MOCK_CHROOT` override, vendor rows land under a different `target` than `stage-mock`/`full-cycle` use #medium
- **BUG-0020** `full-cycle.py` never calls `prepare_stage()` for the vendor stage, and its vendor branch treats a stored `state == "skipped"` as cached -> a vendor row skipped once with reason "spec failed" is permanent; after the spec is fixed the tarball is never generated and srpm later fails on the missing Source1 #high
- **BUG-0024** `go mod vendor` / `cargo vendor` run with no timeout at all; the Makefile forwards `CMD_TIMEOUT` and nothing on the vendor path reads it -> a hung vendor invocation blocks `update-daily` indefinitely #high
- **BUG-0027** `stage-vendor.py:run_for_package` records a missing spec row (`spec_entry is None`) with reason "spec failed" (misleading -- there was no spec run at all), and doesn't special-case spec `state == "skipped"` #low
- **BUG-0028** `eww` extracts its vendor tarball twice: an explicit `tar xf %{SOURCE1}` in `build.prep` in packages.yaml *and* `stage-spec.py`'s auto-inject for any cargo package whose `archives[1]` contains "vendor" #low
- **BUG-0029** that auto-inject (`stage-spec.py`) is cargo-only, positional (`archives[1]`), and substring-matched -> reordering sources, or a Go package with the same two-source layout, silently gets no extraction #low

## Docs / templates

- **BUG-0030** `templates/_contributors.j2`'s `{% if c.github_user %}...{% endif %}` is a block
  tag, and the shared Jinja env sets `trim_blocks=True` -> the newline right after `{% endif %}`
  is eaten on every loop iteration, so contributor entries render concatenated on one line with
  no `-` before the second name (e.g. `Vladimir Budylnikov- Vladimir nett00n Budylnikov`, and the
  name is duplicated because `collect_contributors()` in `gen-report.py` dedupes by exact `git
  log --format=%an` string, and the same person has committed under two different `user.name`
  values). `_authors.j2`/`_maintainers.j2` don't hit this since their loop body has no `{% if %}`.
  Fix needs both: a `{%- endif -%}` (or restructure without the inline if) in the template, and
  `collect_contributors()` deduping by email instead of name #low
- **BUG-0031** generated docs (`README.md`, `docs/README.copr.md`, `docs/full-report.md`) are
  committed with nothing verifying they still match `packages.yaml`/`build-report.db` -> hand-edit
  `packages.yaml` and forget `make readme`, and the README silently lies. A CI step running
  `make readme && git diff --exit-code` would catch it, but `build-report.db` is gitignored so
  CI has no build history to render from -- needs a design decision (commit a report snapshot? skip
  the COPR-status-dependent parts of the diff check?) before it can be added #medium
- **BUG-0032** `lint-ruff` runs before `lint-flake` in the `lint` target's prerequisite list, but
  `requirements-dev.txt` (which installs ruff/mypy/yamllint/rpmlint) is only ever `pip install`ed
  inside `lint-flake`'s recipe -> a genuinely fresh `.venv` (post `make setup-venv`, which only
  installs `requirements.txt`) fails `make lint`/`make pre-commit` at the first sub-target with
  "ruff: command not found". Has gone unnoticed because every local `.venv` in practice already
  has the dev tools from a prior run (the CI workflow works around it by installing
  `requirements-dev.txt` explicitly before `make lint`). `make update-daily` no longer runs
  `lint` (or `pre-commit`) at all -- it only needs `validate-packages`/`fmt` -- so this is back
  to a local annoyance, not a nightly-blocking one (see docs/CHANGELOG.md 2026-08-02) #low

## update-daily

`make update-daily` (Makefile) chains update-versions -> pre-commit -> full-cycle -> readme ->
copr-description -> git commit -> optional push, and is documented (docs/operations.md) as the
unattended nightly job. Audited end to end 2026-08:

- **BUG-0036** Copr preflight is dropped on the `full-cycle` path: `full-cycle.py` calls
  `check_copr_credentials()` and throws away the returned boolean (`stage-copr.py:main()` exits 2
  on the same check), and `validate_copr_repo()` is never called on this path at all -- only in
  `stage-copr.py:main()`. `make update-daily COPR_REPO=<typo>` or an expired token runs the whole
  multi-hour build for 45 packages and only fails at the very end, once per package #high
- **BUG-0039** the published docs always describe builds whose outcome isn't known yet.
  `full-cycle` submits with `--nowait` (async is the default; `update-daily` never sets
  `SYNCHRONOUS_COPR_BUILD`), so a build lands in build-report.db as `state="unknown"`. `make
  readme` runs seconds later, and `lib/copr.py:poll_copr_status()` is a single-shot poll with no
  wait or retry -- every build is still non-terminal, so README.md, docs/full-report.md, and the
  Copr project description pushed by `copr-description` are committed and published describing
  pending builds. They're only corrected ~24h later by the next run #medium
- **BUG-0040** `poll_copr_status()` maps only `succeeded`/`failed`, by substring-matching lines of
  the whole `copr-cli status` output. Any other terminal state (`canceled`, `skipped`, an import
  that never completes) never reaches `TERMINAL_STATES`, so the row stays `unknown` forever --
  re-polled every night, and (per BUG-0002) resubmitted every night #medium
- **BUG-0042** `CMD_TIMEOUT=""` in `.env` crashes every subprocess call. The Makefile's
  quote-stripping covers only `FEDORA_VERSION`/`COPR_REPO`/`PACKAGE`/`SKIP_PACKAGES`, so
  `CMD_TIMEOUT=""` survives as the literal two-character string `""`; make's
  `$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),)` sees it as non-empty and emits
  `CMD_TIMEOUT=""`, the shell strips the quotes, and `run_cmd` does
  `int(os.environ.get("CMD_TIMEOUT", 3600))` on an empty string -> `ValueError`. Same root cause
  as BUG-0008 but a hard crash, not a silent no-op flag (`.env.example` quotes every value it
  ships, so the habit is established) #high
- **BUG-0043** no concurrency guard on a job documented as cron-driven. Nothing takes a lock: 45
  packages at up to `CMD_TIMEOUT=3600s` *per command* can easily outrun the cron interval, and two
  overlapping runs write the same build-report.db, the same rpmbuild-*/local-repo-* podman
  volumes, the same packages.yaml, and the same git index #high
- **BUG-0044** the quality gate never sees the file that gets committed. Order is
  `update-versions -> pre-commit (validate + lint + fmt) -> full-cycle`, but `full-cycle` calls
  `update_package_releases()`, which rewrites packages.yaml in place *after* the gate has run (via
  the regex of BUG-0011). The packages.yaml that lands in the daily commit is the post-regex one,
  which validate-packages.py, yamllint, and format-yaml.py never inspected #high
