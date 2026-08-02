Cleanup, complexity, and unbuilt features. Automation behaving wrong today goes in
`docs/bugs.md` instead. Entries are deleted when done (the fix gets a `docs/CHANGELOG.md`
bullet); IDs are never reused or renumbered, so deletions leave gaps.

## Next

- **Vendor storage redesign** (TODO-0001–TODO-0007, below) — corrupts the submodule checkout on
  the host today, tagged `#high` by design
- **TODO-0041** — 9 scripts (incl. the pre-commit gate itself) have zero tests, violates the
  project's own TDD rule
- **TODO-0033** — package add/delete logic lives in untestable Makefile recipes instead of
  scripts/
- **TODO-0029** — `PACKAGE` means three different things depending on target, no validation
- **TODO-0061** — `update-daily` is all-or-nothing: one failed package aborts before docs/commit,
  losing the night's version bumps
- **TODO-0064** — nightly runs the full developer lint/test gate instead of just validating
  packages.yaml, so an unrelated lint regression blocks all Copr publishing

# Vendor storage #high

Design flaws in `make stage-vendor`; needs a proper design pass, not a patch:

- **TODO-0001** vendoring must never write inside `submodules/` -> `vendor_rust.py`'s submodule
  path rmtrees `vendor/`/`.cargo/` in the live checkout and writes `.cargo/config.toml`
  back into it, as root -> repo working tree trashed, root-owned files, submodule
  permanently dirty (see docs/bugs.md BUG-0021). Needs a scratch
  workspace (copy/`git archive` the submodule out first); the submodule must stay
  read-only input
- **TODO-0002** no stable vendor artifact store -> today storage is just "a file happens to exist in
  `~/rpmbuild/SOURCES`": no input hashing, no invalidation, no ownership, stale tarballs
  win forever (see docs/bugs.md BUG-0023). Want: one documented location
  keyed by (package, version, target/lang), recorded in the `artifacts` table like
  SRPMs/RPMs, invalidated by the same input hashes the other stages use, GC-able via
  `db-prune`
- **TODO-0003** Rust source-tarball generation is a hidden second job of the vendor stage
  (`hyprland-per-window-layout` gets its `%{name}-%{version}.tar.gz` only as this side
  effect, see docs/bugs.md BUG-0022) -> split out or make explicit in the design above
- **TODO-0004** nothing verifies vendoring actually worked -> local mock has network (no
  `rpmbuild_networking = False` in `mock-local-repo.conf`), so an incomplete vendor
  tree builds fine locally and only fails on COPR where network is off;
  `lib/log_analysis.py` already has a rule for "cargo failed to download crate —
  network/DNS error", i.e. this has been hit in production. The one property vendoring
  exists to provide is never tested before submitting. Options: force offline in the
  local mock chroot, or smoke-test the vendor tree (`go build -mod=vendor`,
  `cargo build --offline`) inside the vendor stage
- **TODO-0005** no validation of the vendor tree's contents -> docs/packaging.md itself says
  git-source crates are unresolvable offline, but `cargo vendor`'s output is never checked for
  them; the stage reports success and the failure surfaces two stages later
- **TODO-0006** vendor tarballs are stored per-Fedora-version (`rpmbuild-$(FEDORA_VERSION)` volume,
  DB rows keyed by `target`) though the tree is distro/arch-independent -> the same
  vendor tree is re-downloaded and rebuilt once per Fedora version. Fold into the
  artifact-store design above
- **TODO-0007** toolchain skew: vendoring uses the container's `golang`/`cargo`, the build uses the
  mock chroot's -> a `toolchain` directive in `go.mod` resolved at vendor time can't be
  satisfied offline in the chroot

# Features

- **TODO-0008** Add ARM64 local build support. We did not encounter arch-tangled errors. Yet
- **TODO-0009** Add cross-os-version build matrix visualization
- **TODO-0010** Separate prod builds and local debug ones (?)
- **TODO-0011** add make fmt after scaffolding
- **TODO-0012** \*-git packages to separate block
- **TODO-0013** #2.0 split management system and hyprland repo content. Make automations repo a submodule of content repo (?)

# Containers / caches

- **TODO-0014** `/var/lib/mock` (mock's own chroot cache) isn't mounted as a volume like `rpmbuild`/`local-repo` are -> since containers run `--rm`, every fresh `make stage-mock` run rebuilds/bootstraps the whole chroot from scratch instead of reusing a cached one, costing real time on every `update-daily`. Would need cache-invalidation handling if persisted, since a stale local-repo (see bugs.md) could then poison a persisted chroot's dnf cache too

# Build report db

Migrated from build-report.yaml to build-report.db (sqlite, stdlib) -- see git
history for the migration. Composite key is now `(package, stage, target)`,
row upserts instead of full-file rewrites, and an `artifacts` table tracks
disk usage (`make db-usage`/`make db-prune`). Remaining gaps:

- **TODO-0015** only "last attempt" is stored per (package, stage, target), not "last success" -> a failed rebuild overwrites the previous known-good version/log/build_id, no `last_success` kept alongside `last_attempt`
- **TODO-0017** export sqlite -> yaml/json snapshot for offline diffing (`make db-export`)
- **TODO-0018** artifact sha256 to detect corrupted local-repo RPMs
- **TODO-0019** see docs/bugs.md BUG-0017 (`db-prune` is newest-by-mtime only, no real NVR comparison)
- **TODO-0020** `db-shell`/`db-usage`/`db-prune` only resolve correctly inside the container (artifact paths are container-absolute); no host-side fallback

# Build matrix (arch / non-fedora distros)

- **TODO-0021** db key is already `target` (= mock chroot, e.g. fedora-44-x86_64) and `runs` carries
  distro/distro_version/arch, so aarch64 and centos need no schema change. Everything else
  is still fedora+x86_64-only:
- **TODO-0022** FEDORA_VERSION is the only env knob; needs a TARGET (or DISTRO+ARCH) var, and
  SUPPORTED/mock_chroot()/Containerfile FROM are all fedora-hardcoded
- **TODO-0023** podman volumes are keyed rpmbuild-$(FEDORA_VERSION) / local-repo-$(FEDORA_VERSION);
  need the arch in the name or two arches clobber each other
- **TODO-0024** aarch64 builds need qemu-user-static binfmt or a native runner; mock --forcearch is
  not enough for real cross-arch
- **TODO-0025** packages.yaml has `fedora:` override blocks only -> need distro-agnostic override keys,
  and `lib/version.py:nvr()` hardcodes the .fcNN dist tag (centos wants .el10)
- **TODO-0026** `artifacts` has no arch column; a noarch subpackage's arch != its target's arch
- **TODO-0027** copr rows are keyed by the local mock target, but COPR fans out to its own chroots ->
  a real matrix needs copr rows keyed by the COPR chroot instead
- **TODO-0028** gen-report/templates assume one target per report (`run.fedora_version`); a matrix view
  needs a package x target grid (see also "cross-os-version build matrix visualization")

# Makefile

- **TODO-0029** PACKAGE var means 3 different things (single name / comma-list in set-release / rpm path in gather-requires) with no validation -> split into separate vars or document+enforce per-target
- **TODO-0030** two different multi-package loop strategies coexist: Makefile-side `_PKGS` loop (sources, stage-log-analyze) vs pass-PACKAGE-to-python (all stage-* targets) -> pick one
- **TODO-0031** HIGHLIGHT_PREFIX default bakes literal quote chars into value as a hack so unquoted `echo $(HIGHLIGHT_PREFIX) "text"` works; check-image/check-venv/setup-volumes instead embed it inside a quoted string -> fragile, one edit away from breaking output. simplify to plain value + consistent quoting everywhere
- **TODO-0032** ALL_PACKAGES parses packages.yaml with a grep regex instead of the yaml lib used everywhere else (scripts/*.py, inline python in delete-package/add-submodule) -> fragile, switch to yaml
- **TODO-0033** delete-package/add-submodule/add-new embed real logic (yaml edits, git submodule surgery) directly in Makefile recipes instead of scripts/*.py -> untestable by pytest, move to scripts
- **TODO-0035** delete-package purges rpmbuild-* volumes for removed package across SUPPORTED versions but never touches local-repo-* volumes -> stale RPMs linger

# Scripts

- **TODO-0036** `scripts/gen-spec.py` (~440 lines) duplicates `lib/github.py` (release cache, changelog) and `lib/config.get_packager` almost verbatim, has no Makefile target, unused except by its own test -> looks like a dead pre-pipeline prototype, remove or replace with lib calls
- **TODO-0038** `tests/conftest.py` and `tests/integration/conftest.py` are ~95% identical (fake_repo/minimal_package fixtures copy-pasted), even though tests/integration/ already inherits the parent conftest -> dedupe
- **TODO-0039** `scripts/full-cycle.py:run_build_pipeline` has ~320 lines of repeated per-stage orchestration (spec/vendor/srpm/mock/copr all same shape: cache check -> run_for_package -> build_db.finalize_stage) -> candidate for a small stage-runner abstraction
- **TODO-0040** each `stage-*.py` (validate/spec/vendor/srpm/mock/copr) copy-pastes its own "config: skip" result dict (~6-8 lines x6) -> extract to a small helper (the old `lib/stage_utils.py` was removed in the sqlite migration, its one function unused; a new home is needed for this)
- **TODO-0041** 9 top-level scripts have zero tests: format-yaml, gather-requires, list-tags, pkg-build-pop, pkg-log-analysis, rpm-dir-prefixes-convert, set-package-release, sort-yaml-lists, validate-packages -> violates project's own TDD rule; worst offenders are the two regex-based YAML block parsers (sort-yaml-lists.py, rpm-dir-prefixes-convert.py) and validate-packages.py itself (the pre-commit gate)
- **TODO-0042** `scripts/lib/log_analysis.py` (944 lines) is ~30 copy-pasted `if m: issues.append(...); continue` blocks from hand-written regexes -> a data table of (regex, formatter) pairs would cut it by half+
- **TODO-0043** `vendor_golang.py`/`vendor_rust.py` hand-roll subprocess+log-writing instead of using `lib/subprocess_utils.run_cmd`, which already does exactly that
- **TODO-0044** `vendor.py`/`vendor_golang.py`/`vendor_rust.py` have asymmetric interfaces (Go: dispatcher downloads+extracts then calls generate(src_dir); Rust: generate() does its own download/extract/tarball internally) -> no shared per-language template, drifted independently
- **TODO-0045** 3 YAML modules (`yaml_config.py`, `yaml_utils.py`, `yaml_format.py`) mix PyYAML-load + ruamel-dump inconsistently with no doc on which to use when -> confusing for newcomers
- **TODO-0046** dead code: `lib/reporting.badge()` (only `badge_short()` is used), `lib/yaml_utils.load_packages` alias (only `get_packages` is used) -> remove
- **TODO-0047** `scripts/set-package-release.py` has a redundant manual `sys.path.insert` that no other script needs -> remove
- **TODO-0048** `scripts/serve.py` (dev HTTP server) has no Makefile target and no tests, only mentioned in docs/operations.md -> confirm still needed or drop
- **TODO-0049** `scripts/pkg-log-analysis.py` imports underscore-prefixed "private" functions directly from `lib.log_analysis` -> either make them public API or move this script's logic into lib/
- **TODO-0050** `Containerfile` installs cargo/golang/mock/rpmlint with no version pins -> minor reproducibility risk over time
- **TODO-0052** vendoring is triggered by `build_requires` containing `golang`/`cargo` (two sources of truth with packages.yaml's Source1 + `tar xf %{SOURCE1}`, which must be hand-added and isn't cross-validated) -> silent breakage if the pair drifts
- **TODO-0053** language selection in `lib/vendor.py` is substring matching on `build_requires` while `lib/detection.py` already detects build systems properly -> a package listing both `golang` and `cargo` silently takes the Rust path (Go is checked first only because of call order)
- **TODO-0054** dead `except TypeError` Python<3.12 tarfile-filter fallback in `vendor._extract()`
- **TODO-0055** Go vendor path cleans `tmpdir` twice (in the `except` handler and again in `finally`) and can still log "tmpdir kept" after the dir was already deleted -> `keep_tmpdir` doesn't do what it says
- **TODO-0056** `_log_fn`/`_download`/`_extract` in `lib/vendor.py` are underscore-private but imported directly by `vendor_golang.py`/`vendor_rust.py` -> same smell already noted for `pkg-log-analysis.py` above
- **TODO-0057** `_download()` in `lib/vendor.py` reads the whole archive into memory instead of streaming to disk
- **TODO-0058** vendor stage's `log` field is only recorded on the generate path, not the "tarball already exists" skip path -> inconsistent stage rows
- **TODO-0059** `SOURCES_DIR.mkdir()` only happens in `stage-vendor.py:main()`, not in `run_for_package()` -> the `full-cycle.py` path (which calls `run_for_package` directly) relies on the dir already existing
- **TODO-0060** no test covers `vendor_rust.py`'s submodule branch (the one that mutates the repo working tree, see docs/bugs.md BUG-0021) -> all existing vendor tests exercise the download path only

# Daily update

Design/complexity items found while auditing `make update-daily` end to end (2026-08). Automation
actually misbehaving from these findings is logged in docs/bugs.md's `## update-daily` section
instead.

- **TODO-0061** `update-daily` is all-or-nothing: every step is chained `|| exit 1`, so one
  package failing mock aborts before `readme`/`copr-description`/`git commit` and the night's
  version bumps and submodule moves are left uncommitted in the working tree -- which the next
  run then builds on top of. Want: record and report build failures, still produce docs and the
  commit
- **TODO-0062** `lib/cache.py:_content_hash()` and `_package_config_hash()` are byte-identical
  implementations -- both drop `release`, normalize keys, then sha256 of
  `json.dumps(..., sort_keys=True, default=str)` -- and `compute_input_hashes()` stores both
  results, under `content` *and* `package_config`. Two names, one hash, stored twice in every
  stage row. Collapse to one
- **TODO-0063** `full-cycle.py` sleeps 5 seconds after printing the build plan "before
  proceeding" -- an interactive abort window that only burns time in the unattended cron flow the
  target is documented for. Gate on a TTY or an env flag
- **TODO-0064** the nightly runs the full *developer* gate: `pre-commit` = `validate-packages` +
  pytest + ruff + flake8 + mypy + rpmlint + yamllint + `fmt`. An unrelated lint regression in
  scripts/ therefore blocks all package updates and the Copr publish. Repo health is already CI's
  job (`.github/workflows/ci.yml` runs lint+test on every push); the nightly only needs "is
  packages.yaml valid". Split the two (this also makes the fresh-venv ordering trap of BUG-0032 a
  nightly-blocking issue, not just a local annoyance)
- **TODO-0065** the nightly builds one `FEDORA_VERSION` (default 43) while `SUPPORTED := 43 44
  rawhide`. There is no loop over versions and no way to express "the nightly covers the matrix",
  so two thirds of the supported set are only ever exercised by Copr's own fan-out. Compounds
  BUG-0018
- **TODO-0066** nothing in the daily flow reports what happened. `make stage-log-analyze` exists
  and is never called by `update-daily`; the only durable output is a commit message containing a
  timestamp. Want a nightly summary artifact -- or at minimum, run log-analyze on failure *before*
  BUG-0041 deletes the logs
- **TODO-0067** `make readme` starts three separate containers to render three templates from the
  same build-report.db, and only the first (`github`) polls Copr -- the other two pass
  `--skip-copr-poll` and read whatever the first left behind. One invocation rendering all three
  would be cheaper and could not drift
- **TODO-0068** `update-versions.py` force-pulls 45 submodules and fetches tags for 45 packages
  serially on every run, with no concurrency, no offline mode, and no aggregate failure report: an
  individual `git fetch` failure prints a warning and is then invisible in the stdout summary, so
  a package can silently sit on a stale version indefinitely
- **TODO-0069** `lib/yaml_utils.write_yaml_preserving_comments()` does not preserve comments --
  its own docstring says so ("accepted trade-off for simpler code"). Misleading name on the
  function that rewrites packages.yaml on every nightly run. Rename

# Packages

Moved to `docs/package-requests.md`.
