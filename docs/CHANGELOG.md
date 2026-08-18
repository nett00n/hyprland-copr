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

## 2026-08-18

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
