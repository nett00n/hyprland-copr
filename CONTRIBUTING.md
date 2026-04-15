# Contributing

## Repository Layout

```
packages.yaml                      # single source of truth — metadata for all packages
packages/<name>/<name>.spec        # generated spec files (committed, editable)
templates/spec.j2                  # Jinja2 spec template
templates/readme-github.md.j2      # Jinja2 template for GitHub README
templates/readme-copr.md.j2        # Jinja2 template for COPR README
templates/full-report.md.j2 # Jinja2 template for detailed build report
templates/_*.j2                    # Jinja2 snippet: simple, no includes
templates/__*.j2                   # Jinja2 snippet: composite, includes other snippets
templates/packages-entry.yaml.j2   # Jinja2 template for new packages.yaml entries
scripts/full-cycle.py              # full build orchestrator: spec → vendor → srpm → mock → copr
scripts/gen-report.py              # renders build report from build-report.yaml (--format github|copr|full-report, --output FILE)
scripts/scaffold-package.py        # scaffolds a new packages.yaml entry from a submodule
scripts/update-versions.py         # fetches latest submodule tags and updates packages.yaml
scripts/pkg-log-analysis.py        # analyzes build logs for actionable errors
scripts/stage-validate.py          # stage 0: validate packages.yaml entries
scripts/stage-spec.py              # stage 1: generate spec files
scripts/stage-vendor.py            # stage 1b: generate Go vendor tarballs
scripts/stage-srpm.py              # stage 2: build SRPMs
scripts/stage-mock.py              # stage 3: local mock build
scripts/stage-copr.py              # stage 4: submit to Copr
scripts/stage-show-plan.py         # show build plan (what will run, cache, or skip)
scripts/format-yaml.py             # YAML formatter invoked by `make fmt-yaml`
scripts/serve.py                   # dev convenience: local HTTP file server for build artifacts
scripts/lib/                       # shared library modules for all pipeline scripts
requirements-dev.txt               # Python deps (jinja2, pyyaml, mypy, ruff, yamllint, flake8, rpmlint)
submodules/<org>/<name>/           # upstream sources as git submodules
```

### Template Snippet Naming Convention

Jinja2 snippets use a naming convention to indicate dependencies:

- **Single dash (`_*.j2`)** — Leaf snippets with no includes. Examples: `_logo.j2`, `_description.j2`, `_badge.j2`
- **Double dash (`__*.j2`)** — Composite snippets that include other snippets. Examples: `__header.j2`, `__footer.j2`

This makes it easy to understand the composition graph and avoid circular dependencies.

## Package Groups

`packages.yaml` has a top-level `groups` section that controls how packages appear in the
build report. A package can belong to multiple groups.

```yaml
groups:
  hyprland:
    label: "Hyprland main packages"
    packages:
      - Hyprland
      - hypridle

  hyprland-deps:
    label: "Hyprland dependencies"
    packages:
      - hyprutils
      - hyprlang

  apps:
    label: "Useful apps"
    packages:
      - aylurs-gtk-shell

  deps:
    label: "Other dependencies"
    packages:
      - glaze
```

When adding a new package, add it to the appropriate group(s) in the `groups` section.
Packages absent from all groups still appear in the raw `packages` list but are omitted
from the grouped build report.

## Adding a New Package

The easiest path is the single-command workflow:

```shell
make add-new URL=https://github.com/org/repo
```

This registers the submodule and scaffolds the `packages.yaml` entry in one step.

Alternatively, step by step:

1. View available submodules and their latest tags (optional):
   ```shell
   make list-tags PACKAGE=<name>  # list tags for one package
   make list-tags                 # list tags for all submodules
   ```

2. Add repository as a submodule:
   ```shell
   git submodule add <url> submodules/<org>/<name>
   make add-submodule PACKAGE=<name>  # register it in git (same as step 1 above)
   ```

3. Build container image: `make container-build` (or `make container-all` for all Fedora versions)

1. Create virtualenv if not exist: `make setup-venv`

1. Execute: `make scaffold-package PACKAGE=<name>` with your package instead of `<name>`

1. New entry would be added to `packages.yaml`:

   ```yaml
   packages:
     <name>:
       version: "1.2.3"
       release: "%autorelease"
       license: MIT
       summary: One-line description
       description: |
         Longer description.
       url: https://github.com/org/<name>
       source_name: <name>  # set if tarball top-level dir differs from package name (e.g., git packages where package is "foo-git" but repo is "foo")
       sources:             # auto-indexed: Source0, Source1, ...
         - url: "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
       build_system: cmake  # cmake | meson | autotools | make
       depends_on:          # local packages that must be built first (authoritative)
         - hyprutils        # add any local packages referenced in build_requires
       build_requires:
         - cmake
         - pkgconfig(wayland-client)
       files:
         - "%license LICENSE"
         - "%{_bindir}/<name>"
   ```

   The `depends_on` field lists other packages from this repo that must be built
   before this one. It is the authoritative source for dependency ordering — it
   overrides the `-devel` heuristic used when the field is absent. The
   `scaffold-package.py` script auto-detects `depends_on` from `build_requires`
   entries that match existing package keys (both `-devel` and `pkgconfig()` forms).
   `make stage-validate` will warn about any `build_requires` entries that reference
   local packages but are missing from `depends_on`.

1. Update FIXME fields with your ones

1. Start build cycle:

   ```shell
   make full-cycle PACKAGE=<name> FEDORA_VERSION=43 COPR_REPO=nett00n/hyprland
   # Default variable values:
   # FEDORA_VERSION=43
   # PACKAGE= (or PKG=) — all packages if unset
   # COPR_REPO= — no push to Copr if unset
   ```

1. This would execute spec generation to `packages/<name>/<name>.spec`,
   srpm creation and local build

1. Check build logs in `logs/`

1. If the build failed, analyze logs for actionable errors:

   ```shell
   make stage-log-analyze PACKAGE=<name>
   ```

   This parses mock/srpm logs and reports:
   - Missing dependencies and suggested packages
   - Incompatible plugins (internal header errors)
   - Missing source files (broken submodules)
   - Other compile errors with line references

1. Fix issues in `packages.yaml` (add `build_requires`, exclude incompatible plugins, etc.) and retry

1. Verify with rpmlint:

```shell
rpmlint packages/<name>/<name>.spec
```

13. Commit, make PR

## Utility Commands

### Download Sources

Pre-download sources for a package using `spectool` (useful for offline builds or debugging):

```shell
make sources PACKAGE=<name>  # download for one package
make sources                 # download for all packages
```

### Suggest Requires

After building an RPM, analyze its dependencies and suggest `requires` entries:

```shell
make gather-requires PACKAGE=path/to/package.rpm
```

Pass the path to a built `.rpm` file. Reports SONAME dependencies and suggests `requires:` entries for `packages.yaml`.

### Remove Package

Completely remove a package from the repository (deletes from `packages.yaml`, build logs, spec files, submodules, and container volumes):

```shell
make delete-package PACKAGE=<name>
```

Or using the `PKG` alias:

```shell
make delete-package PKG=<name>
```

### Clear Build Status

Reset the build status for one or more packages in `build-report.yaml`:

```shell
make build-pop PKG=pkg1,pkg2    # remove status for specific packages
make build-pop PKG=""            # remove status for ALL packages (requires confirmation)
```

This is useful after fixing issues to force a re-run without manual YAML editing.

### Go packages

If the package has a Go CLI or library, add `golang` to `build_requires`.
The vendor stage will automatically generate a `<name>-<version>-vendor.tar.gz`
and place it in `~/rpmbuild/SOURCES/` before the SRPM is built.

If the `go.mod` is not at the tarball root (e.g. lives in `cli/`), add:

```yaml
go_subdir: cli
```

Then add the vendor tarball as Source1 and extract it in `prep_commands`:

```yaml
sources:
  - url: "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
  - url: "%{name}-%{version}-vendor.tar.gz"
prep_commands:
  - "pushd cli"
  - "tar xf %{SOURCE1}"
  - "popd"
```

To generate the vendor tarball manually (outside the full pipeline):

```shell
make stage-vendor PACKAGE=<name>
```

**Why Go vendoring works:** `go mod vendor` automatically includes all dependencies (including git sources) in `vendor/`, and Go checks `vendor/` first during builds with no special configuration needed.

### Rust packages

Rust packages do **not** use vendoring. Instead, they follow the canonical COPR/Fedora approach:
- Build all Rust dependencies as separate RPM packages
- Use system-installed crates instead of bundled sources
- This is simpler, follows Fedora guidelines, and avoids git dependency issues

**Rationale:** Rust git dependencies cannot be properly handled in offline COPR builds yet

### Shared Libraries (`scripts/lib/`)

- **cache.py** — input hash computation for caching and build invalidation
- **config.py** — configuration helpers (packager info from env/git, logging setup)
- **copr.py** — Copr API interaction and build status polling
- **deps.py** — dependency graph inference from `depends_on` and `build_requires`
- **detection.py** — license and Meson dependency detection from build files
- **github.py** — GitHub API helpers (release info caching, changelog generation)
- **gitmodules.py** — `.gitmodules` parsing, submodule commit/tag info extraction
- **jinja_utils.py** — Jinja2 environment setup
- **log_analysis.py** — parsing mock/srpm logs for failure reporting
- **paths.py** — canonical path constants (`SOURCES_DIR`, `BUILD_STATUS_YAML`, etc.) and helpers (`mock_chroot()`)
- **pipeline.py** — build pipeline state management and caching helpers
- **reporting.py** — build status printing and badge generation
- **rpm_macros.py** — RPM macro path normalization (e.g., `/usr/bin/foo` → `%{_bindir}/foo`)
- **stage_utils.py** — shared utilities for stage scripts (`make_stage_entry()`, etc.)
- **subprocess_utils.py** — subprocess wrappers with timeout support (`run_cmd`, `run_git`)
- **tarball.py** — tarball source name detection via streaming curl|tar
- **validation.py** — package metadata validation (files, versions, groups, gitmodules)
- **vendor.py** — Go package vendoring wrapper with Python 3.10+ compatibility
- **vendor_golang.py** — Go module vendoring with `go mod vendor`
- **vendor_rust.py** — ABANDONED: Rust crate vendoring (git deps are unresolvable in offline builds; Rust uses COPR native approach instead)
- **version.py** — semantic version parsing and selection
- **yaml_format.py** — YAML formatting with literal block scalar support, yamllint config parsing
- **yaml_utils.py** — loading/saving packages.yaml, filtering, build status tracking, `init_stage()` boilerplate helper

## Package Version Auto-Updates

The `update-versions.py` script manages version updates for submodule-based packages. The `auto_update` field in `packages.yaml` controls the update strategy per package.

### Basic auto_update Configuration

```yaml
package-name:
  auto_update:
    release_type: latest-commit  # or: latest-version, pinned-version, pinned-commit, pinned-tag
    branch: dev                   # optional: override default branch
  url: https://github.com/org/repo
  version: "0.53.0"
```

### Release Types

| Type | Behavior | Extra Fields | Version Format |
|------|----------|--------------|---|
| `latest-version` | Latest semver tag only, no commit fallback | `branch` | `1.2.3` |
| `latest-commit` | Latest HEAD commit on branch | `branch` | `1.2.3^20240101gitabc1234` |
| `pinned-version` | Skip updates entirely (manual control) | `version` | - |
| `pinned-commit` | Skip updates entirely (manual control) | `commit` | - |
| `pinned-tag` | Track specific named non-semver tag | `tag` | `0.53.0^20240101gitabc1234` |
| *(absent)* | Default: try semver, fall back to commit | `branch` | `1.2.3` or `0^20240101gitabc1234` |

### Version Format for Commit-Based Types

For `latest-commit` and `pinned-tag`, versions use the nearest reachable semver tag as a prefix:
- `0.53.0^20240101gitabc1234` — commit is after `v0.53.0` tag
- `0^20240101gitabc1234` — no semver tag reachable

When `source.commit` exists (for archive-based sources), it is automatically populated with the full hash and date.

### Examples

**Hyprland plugins on dev branch (latest commits only):**
```yaml
hyprland-plugins:
  auto_update:
    release_type: latest-commit
    branch: dev
  url: https://github.com/hyprwm/hyprland-plugins
  version: "0.53.0^20260223gitb85a56b"
```

**Pinned release (no auto-updates):**
```yaml
some-stable-lib:
  auto_update:
    release_type: pinned-version
    version: "1.0.0"
  url: https://github.com/org/some-stable-lib
```

**Track nightly builds:**
```yaml
nightly-pkg:
  auto_update:
    release_type: pinned-tag
    tag: nightly
  url: https://github.com/org/nightly-pkg
  version: "0^20260101gitnightly123"
```

### Running the Update Script

```shell
# Pull latest submodules and update versions based on auto_update config
python3 scripts/update-versions.py

# Commit changes if updates were made
git add packages.yaml && git commit -m "Update package versions"
```

## Code Quality and Linting

The repository uses multiple linters and formatters to maintain code quality. All checks run inside a container (podman/docker, auto-detected):

### Setup (one-time)

```shell
make setup-venv   # creates .venv and installs requirements.txt (runtime deps)
make container-build   # build container image for Fedora 43 (or FEDORA_VERSION=X for specific version)
```

### Running checks and formatting

```shell
# Run all linters (inside container, installs dev tools on first run)
make lint    # lint-ruff + lint-flake + lint-mypy + lint-rpm + lint-yaml

# Format code
make fmt           # fmt-ruff + fmt-yaml + normalize-paths + sort-lists

# Pre-commit workflow: run all checks + formatting
make pre-commit QUIET=1   # runs: validate-packages + test + lint + fmt
```

**Linter checks:**

- **lint-ruff** — fast Python linter on scripts/
- **lint-flake** — style checker for Python (flake8)
- **lint-mypy** — static type checker for Python
- **lint-rpm** — RPM spec linter (rpmlint)
- **lint-yaml** — validates YAML files (yamllint)

**Format operations:**

- **fmt-ruff** — ruff format for Python
- **fmt-yaml** — YAML formatting
- **normalize-paths** — convert absolute paths ↔ RPM macros
- **sort-lists** — alphabetically sort build_requires, requires, files

All checks automatically exclude `submodules/` directory.

### Logging Levels

All scripts support the `LOG_LEVEL` environment variable to control verbosity:

```shell
# Show everything (traces, debug info)
LOG_LEVEL=DEBUG make stage-validate PACKAGE=hyprland

# Default: info-level messages only
make stage-validate PACKAGE=hyprland

# Quiet: only warnings and errors
LOG_LEVEL=WARNING make stage-validate PACKAGE=hyprland

# Silent: only errors and critical failures
LOG_LEVEL=ERROR make stage-validate PACKAGE=hyprland
```

Levels: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`.

## Local Build Workflow

Prerequisites: a container image built with `make container-build`, and a Python venv:

```shell
make setup-venv   # one-time: creates .venv and installs requirements.txt
make container-build   # one-time: build container image for Fedora 43
```

```shell
# Regenerate spec files
make stage-spec PACKAGE=<name>

# Download sources, build SRPM, test with mock
make stage-srpm PACKAGE=<name>
make stage-mock PACKAGE=<name> FEDORA_VERSION=43
```

### Full Cycle Pipeline Options

The `full-cycle` target supports several flags:

```shell
# Default: build spec → vendor → srpm → mock → copr (if COPR_REPO set)
make full-cycle PACKAGE=<name> FEDORA_VERSION=43

# Resume from interrupted run (skip already-succeeded stages)
make full-cycle PACKAGE=<name> PROCEED_BUILD=true

# Skip mock stage (stop after srpm, useful for quick validation)
make full-cycle PACKAGE=<name> SKIP_MOCK=true

# Skip copr submission (test locally without pushing)
make full-cycle PACKAGE=<name> SKIP_COPR=true

# Wait for COPR builds to complete (default: async with --nowait)
make full-cycle PACKAGE=<name> COPR_REPO=nett00n/hyprland SYNCHRONOUS_COPR_BUILD=true

# Combine options
make full-cycle PACKAGE=<name> SKIP_MOCK=true FEDORA_VERSION=42
```

#### COPR Build Behavior

By default, COPR builds are submitted asynchronously using the `--nowait` flag. This allows `pkg-full-cycle`
to complete immediately after submission without blocking for build completion.

- **Async mode (default):** Submits builds and records the build IDs, pipeline completes immediately
- **Synchronous mode:** Set `SYNCHRONOUS_COPR_BUILD=true` to wait for builds to complete before exiting

#### Build Report Generation

The `gen-report.py` script generates markdown reports from `build-report.yaml`. It supports multiple output formats and COPR status polling:

```bash
# Generate GitHub-style README
.venv/bin/python3 scripts/gen-report.py --format github --output README.md

# Generate COPR README (skips COPR polling for speed)
.venv/bin/python3 scripts/gen-report.py --format copr --output docs/README.copr.md --skip-copr-poll

# Generate full detailed report (skips COPR polling)
.venv/bin/python3 scripts/gen-report.py --format full-report --output docs/full-report.md --skip-copr-poll

# Print to stdout (default behavior)
.venv/bin/python3 scripts/gen-report.py --format github
```

**Arguments:**
- `--format github|copr|full-report` — Report format (default: github)
- `--output FILE` — Write to file instead of stdout
- `--skip-copr-poll` — Skip polling COPR status (use cached status from build-report.yaml)

By default, `gen-report.py` automatically polls COPR for the status of in-progress builds and updates
`build-report.yaml` with the latest state. Use `--skip-copr-poll` when running multiple report generations
to avoid redundant API calls (e.g., `make readme` generates 3 reports but polls COPR only once).

The `make readme` target optimizes this automatically:
- **First call** (GitHub README): Polls COPR status
- **Subsequent calls** (COPR README, Full Report): Skip polling (`--skip-copr-poll`)

### Build Cache and Force Re-run

By default, `full-cycle` skips stages whose inputs haven't changed (hash-based caching).
To force a stage to re-run, edit `build-report.yaml` and set `force_run: true`:

```yaml
stages:
  spec:
    hyprland:
      state: success
      force_run: true    # operator sets to force re-execution
      reason: cached     # auto-set: explains skip/run decision
      version: "0.45.2-1.fc43"
      # ... rest of entry
```

**Rules:**
- Setting `force_run: true` on any stage forces that stage and all downstream stages to re-run
  (intra-package cascade: spec → vendor → srpm → mock → copr)
- If any package in `depends_on` was rebuilt (and not cached) in the current run, all stages of the
  dependent package are forced (inter-package dependency cascade)
- After a stage executes (success or fail), the `force_run` field is automatically removed
  (operator must re-set to force again; one-shot behavior)
- The `reason` field is automatically set on each stage entry to explain why it was cached,
  skipped, or forced to run (e.g., `"cached"`, `"hash-mismatch"`, `"spec failed"`, `"forced (dep rebuilt: hyprutils)"`).
  When showing rebuilt dependencies, only lists deps that actually changed (cached deps filtered out).

### Build Report Backups

At the start of each `full-cycle` run, the existing `build-report.yaml` is automatically backed up
with an RFC 3339 timestamp (filesystem-safe): `build-report.2026-03-21T10-30-45+00-00.yaml`.
This happens before any processing begins, preserving the previous state and allowing rollback if needed.

### Running individual pipeline stages

```shell
# Run stages individually (each reads/writes build-report.yaml)
make stage-validate PACKAGE=<name>   # validate packages.yaml (required fields, conventions)
make stage-spec     PACKAGE=<name>
make stage-vendor   PACKAGE=<name>   # Go packages: generates vendor tarball (skipped for Rust)
make stage-srpm     PACKAGE=<name>
make stage-mock     PACKAGE=<name> FEDORA_VERSION=43
make stage-copr     PACKAGE=<name> COPR_REPO=nett00n/hyprland

# Compose a custom pipeline (e.g. skip copr)
make stage-validate stage-spec stage-vendor stage-srpm stage-mock PACKAGE=<name>
```

`PACKAGE` (or `PKG`) is matched case-insensitively, so `PACKAGE=hyprland` and `PACKAGE=Hyprland` both work.

When `PACKAGE` is set, `full-cycle` automatically includes transitive build dependencies and processes them in topological order.

## Submitting to Copr

Use `full-cycle` with `COPR_REPO` set:

```shell
make full-cycle PACKAGE=<name> COPR_REPO=nett00n/hyprland-extras
```

Or use `stage-copr` alone after building locally:

```shell
make stage-copr PACKAGE=<name> COPR_REPO=nett00n/hyprland-extras
```

Requires `copr-cli` configured with `~/.config/copr`.

## Checklist Before Opening a PR

- [ ] `packages.yaml` entry is complete and correct
- [ ] `make stage-validate PACKAGE=<name>` passes with no errors
- [ ] `rpmlint` passes with no errors
- [ ] Builds cleanly with `make stage-mock PACKAGE=<name>`
- [ ] `Source0:` points to an upstream release tarball (not a manual archive) and uses `#/%{name}-%{version}.tar.gz` suffix to avoid filename collisions between packages at the same version
- [ ] No bundled C/C++ libraries (Go vendor tarballs are acceptable)
- [ ] Changelog entry added with correct date and your name
