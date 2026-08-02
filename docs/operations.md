# Operations — maintainer runbook

Day-to-day running of the pipeline. For adding a package as a contributor, see
`docs/CONTRIBUTING.md`. For `packages.yaml` schema details, see `docs/packaging.md`.

## Local build workflow

```shell
make stage-spec  PACKAGE=<name>                      # regenerate the spec file
make stage-srpm  PACKAGE=<name>                       # download sources, build SRPM
make stage-mock  PACKAGE=<name> FEDORA_VERSION=43     # test-build in mock
```

Or run stages individually and compose a custom pipeline:

```shell
make stage-validate PACKAGE=<name>   # validate packages.yaml entry
make stage-spec      PACKAGE=<name>
make stage-vendor    PACKAGE=<name>   # Go/Rust: generates vendor tarball (no-op otherwise)
make stage-srpm      PACKAGE=<name>
make stage-mock      PACKAGE=<name> FEDORA_VERSION=43
make stage-copr       PACKAGE=<name> COPR_REPO=nett00n/hyprland

make stage-validate stage-spec stage-vendor stage-srpm stage-mock PACKAGE=<name>  # skip copr
```

`PACKAGE`/`PKG` (either name works, case-insensitive) selects one package; unset builds all.
When set, `full-cycle` automatically pulls in transitive build dependencies and orders them
topologically.

### `full-cycle` flags

```shell
make full-cycle PACKAGE=<name> FEDORA_VERSION=43                          # spec→vendor→srpm→mock→copr
make full-cycle PACKAGE=<name> PROCEED_BUILD=true                          # resume, skip already-succeeded stages
make full-cycle PACKAGE=<name> SKIP_MOCK=true                              # stop after srpm
make full-cycle PACKAGE=<name> SKIP_COPR=true                              # test locally, don't push
make full-cycle PACKAGE=<name> COPR_REPO=nett00n/hyprland SYNCHRONOUS_COPR_BUILD=true  # wait for COPR
make full-cycle PACKAGE=<name> COPR_REPO=nett00n/hyprland REQUIRE_CHROOT_COVERAGE=true # block submit on chroot gaps
```

Copr submission runs as its own pass, only after every package in the run has gone through
`mock` — if any package's `mock` stage failed, **no package is submitted**, so a healthy package
never publishes while a sibling in the same dependency set is broken. By default COPR builds are
submitted with `--nowait` (async); `SYNCHRONOUS_COPR_BUILD=true` waits for completion instead.

Before submitting, `full-cycle`/`stage-copr` also print a per-chroot local-mock coverage table
(queried from the Copr project's actual chroot list): each chroot is `verified` (this package's
local mock succeeded for it), `failed`, `unbuilt` (same arch, never tried locally), or `not
verifiable locally` (aarch64 — mock can't cross-build here, see `docs/todo.md` TODO-0024). By
default this only warns and still submits; `REQUIRE_CHROOT_COVERAGE=true` blocks the submission
instead whenever a same-arch chroot is `failed`/`unbuilt` (an aarch64 gap alone never blocks —
there is no local way to close it yet).

### Building every chroot locally before submitting

A single `full-cycle` run only builds one `FEDORA_VERSION`'s x86_64 chroot, but Copr fans a
submission out to every chroot configured on the project (fedora-43/44/rawhide x86_64/aarch64
for `nett00n/hyprland`) — a chroot-specific failure (e.g. a newer libstdc++ needed than an older
Fedora ships) can pass local mock and still fail on Copr (see `docs/bugs.md` BUG-0018). To catch
that before submitting:

```shell
make container-all                                                    # build images for all SUPPORTED versions once
make full-cycle-matrix PACKAGE=<name> COPR_REPO=nett00n/hyprland       # build every MATRIX_VERSIONS chroot locally, then submit once
make full-cycle-matrix PACKAGE=<name> MATRIX_VERSIONS="43 44"          # limit to specific versions
```

This loops `full-cycle FEDORA_VERSION=<v> SKIP_COPR=true` per `MATRIX_VERSIONS` (default: every
`SUPPORTED` version), then submits to Copr exactly once — Copr already fans one SRPM out to all
its own chroots, so submitting per version would create duplicate builds. aarch64 chroots are
still not covered by this (no cross-arch build path locally yet).

### Check build logs

`logs/build/<name>/`: `00-spec`/`10-srpm`/`20-mock`/`21-mock-build`/`21-mock-root` are local
stages. `30-copr` is the Copr submission (and, with `SYNCHRONOUS_COPR_BUILD=true`, the watched
result). On a Copr failure, `30-copr-chroots.log` (per-chroot states) and
`31-copr-<chroot>.log` (downloaded builder logs for the chroots that failed) are fetched
automatically — useful for an aarch64-only failure, which `make full-cycle-matrix` still can't
reproduce locally (see `docs/bugs.md` BUG-0018).

On failure, analyze logs for actionable errors:

```shell
make stage-log-analyze PACKAGE=<name>
```

Reports missing dependencies, incompatible plugins, missing source files, compile errors with
line references, and (for Copr) which chroots failed vs. succeeded.

## Submitting to Copr

```shell
make full-cycle PACKAGE=<name> COPR_REPO=nett00n/hyprland-extras   # full pipeline + submit
make stage-copr PACKAGE=<name> COPR_REPO=nett00n/hyprland-extras   # submit only, after a local build
```

Requires `copr-cli` configured with `~/.config/copr`.

## Build cache and forcing a re-run

`full-cycle` skips stages whose inputs haven't changed (hash-based caching). To force one or
more packages to re-run without a full pipeline run:

```shell
make build-pop PKG=hyprland,waybar   # force re-run for specific packages
make build-pop PKG=""                # force ALL packages (asks for confirmation)
```

This sets `force_run` on the mock/copr rows in `build-report.db`; the next `full-cycle` picks it
up and clears it (one-shot). For a stage other than mock/copr, use `db-shell` directly:

```shell
make db-shell
sqlite> UPDATE stage_results SET force_run = 1
        WHERE package = 'hyprland' AND stage = 'spec' AND target = 'fedora-44-x86_64';
```

Rules:
- Forcing any stage forces it and all downstream stages (spec → vendor → srpm → mock → copr).
- If a `depends_on` dependency was rebuilt (not cached) in the current run, all stages of the
  dependent package are forced too.
- `force_run` is cleared automatically after the stage runs, success or fail (one-shot).
- `reason` on each stage row explains why it was cached/skipped/forced (e.g. `"cached"`,
  `"hash-mismatch"`, `"forced (dep rebuilt: hyprutils)"`) — only lists deps that actually
  changed.

## Build report database

Build state lives in `build-report.db` (sqlite, gitignored), keyed by `(package, stage, target)`
— `target` is the mock chroot (e.g. `fedora-44-x86_64`), so a second Fedora version doesn't
overwrite the first. Three tables: `runs` (one row per invocation), `stage_results` (per-stage
state), `artifacts` (paths/sizes of build outputs). `make db-shell` opens an interactive sqlite3
shell.

Every SRPM, vendor tarball, and mock-built RPM (plus logs) is recorded in the `artifacts` table
as it's produced:

```shell
make db-usage              # disk usage by package × target
make db-prune               # dry-run: what would be removed (keeps newest per package/target/kind)
make db-prune CONFIRM=1     # actually delete
```

`db-prune` only prunes `srpm`/`rpm`/`vendor` — logs are untouched; use `make clean-logs` for
those. Both must run in-container (`CONTAINER_PYTHON`): recorded paths are container-absolute
and only resolve with the same volumes mounted.

`make clean-logs` clears `stage_results`/`runs` but keeps the artifact ledger — dropping it
would orphan every tracked file with no record of what it is. For a full wipe (irreversible,
asks for confirmation): `make db-nuke`.

## Regenerating docs

```shell
make readme   # regenerates README.md, docs/README.copr.md, docs/full-report.md
```

Renders from `build-report.db` via `scripts/gen-report.py` (`--format github|copr|full-report`).
By default it polls COPR for in-progress build status and updates the DB; `make readme` does
this only once (the GitHub README pass) and passes `--skip-copr-poll` for the other two, to
avoid redundant API calls.

### `repo.yaml` reference

Branding/layout config for generated docs -- name, logo, license, support links, badge style,
and (below) the News feed and per-section visibility. Package data itself comes from
`packages.yaml`/`build-report.db`, not this file.

```yaml
documents:
  badge_style: for-the-badge
  news_limit: 8          # how many blog/NEWS.md entries the README shows (default: 8)
  sections:               # per-block visibility in generated docs; unset keys default to true
    news: true
    docs: true
    support: true
    license: true
    authors: true
    maintainers: true
    contributors: true
    additional_info: true  # additional_info also still requires repo.bottom_info to be set
```

Every key under `sections` is independent -- e.g. set `contributors: false` to hide a broken
render (see `docs/bugs.md` BUG-0030) without touching the underlying git-log-based collection
logic. Omitting `documents.sections` entirely renders every block, same as today.

### CI docs-shell publish

`make readme` needs `build-report.db` (gitignored) to know which packages exist and their build
status -- CI starts with none, so it can't run `make readme` safely; doing so would render zero
packages and, if auto-committed, wipe the real README.

```shell
make readme-shell   # regenerate only the branding shell, no build-report.db needed
```

`scripts/gen-readme-shell.py` renders `__header.j2`/`__footer.j2` (logo, description, News,
Docs, Support, License, People) from `repo.yaml`/`blog/NEWS.md`/git log, and splices the result
into `README.md`/`docs/README.copr.md` between their existing `<!-- BEGIN: X -->`/
`<!-- END: X -->` markers -- everything between the header and footer (the packages table,
build status) is left exactly as committed. `docs/full-report.md` isn't touched at all; it's
build-data end to end and stays a `make readme`-local artifact.

`.github/workflows/publish-readme.yml` runs this on every push to `main` and on manual dispatch,
committing (`[skip ci]`, to avoid re-triggering itself) and pushing if anything changed. Safe by
construction: the script cannot touch the packages/build-status region, so there's no path to
an empty-package README landing on `main` even from a from-scratch checkout.

## `update-daily`

```shell
make update-daily COPR_REPO=nett00n/hyprland            # commit only
make update-daily COPR_REPO=nett00n/hyprland PUSH=1      # commit and push
```

Runs: bump versions → quality gate (`pre-commit`: validate + test + lint + fmt) → full build
cycle → regenerate docs → push COPR description → `git commit`. Only stages
`packages.yaml packages/ submodules/ README.md docs/README.copr.md docs/full-report.md` — the
automation never touches `templates/`/`blog/`, so hand-edits there are never swept into a daily
commit. Intended to run unattended from an external nightly cron (the repo itself has no
scheduler); pass `PUSH=1` for that.

A no-op night (nothing staged) skips the commit instead of failing the target. With `PUSH=1`,
the target rebases onto `origin/main` before pushing, so it doesn't collide with
`publish-readme.yml`'s own `[skip ci]` push to `main`.

## Utility commands

**Download sources** (offline/debug):
```shell
make sources PACKAGE=<name>   # or omit PACKAGE for all
```

**Suggest `requires:` entries** from a built RPM's SONAME dependencies:
```shell
make gather-requires PACKAGE=path/to/package.rpm
```

**Remove a package** entirely (`packages.yaml`, build logs, spec files, submodules, container
rpmbuild dirs):
```shell
make delete-package PACKAGE=<name>   # PKG=<name> also works
```

**Dev file server** for build artifacts (not wired into any Makefile target):
```shell
.venv/bin/python3 scripts/serve.py
```

## Logging

`LOG_LEVEL` env var on any script/stage: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`,
`CRITICAL`.

```shell
LOG_LEVEL=DEBUG make stage-validate PACKAGE=hyprland
```
