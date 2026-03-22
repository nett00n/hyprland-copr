# Contributing

## Repository Layout

```
packages.yaml                      # single source of truth — metadata for all packages
packages/<name>/<name>.spec        # generated spec files (committed, editable)
templates/spec.j2                  # Jinja2 spec template
templates/readme-github.md.j2      # Jinja2 template for GitHub README
templates/readme-copr.md.j2        # Jinja2 template for COPR README
templates/readme-full-report.md.j2 # Jinja2 template for detailed build report
templates/_*.j2                    # Jinja2 snippet: simple, no includes
templates/__*.j2                   # Jinja2 snippet: composite, includes other snippets
templates/packages-entry.yaml.j2   # Jinja2 template for new packages.yaml entries
scripts/full-cycle.py              # runs the complete pipeline end-to-end
scripts/gen-spec.py                # renders specs from packages.yaml + templates/spec.j2
scripts/gen-report.py              # renders the build report from build-report.yaml
scripts/gen-vendor-tarball.py      # standalone: generate Go vendor tarball for one package
scripts/scaffold-package.py        # scaffolds a new packages.yaml entry from a GitHub URL
scripts/stage-validate.py          # pipeline stage: validate packages.yaml entries
scripts/stage-spec.py              # pipeline stage: generate spec files
scripts/stage-vendor.py            # pipeline stage: generate Go vendor tarballs
scripts/stage-srpm.py              # pipeline stage: build SRPMs
scripts/stage-mock.py              # pipeline stage: local mock build
scripts/stage-copr.py              # pipeline stage: submit to Copr
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

1. Add repository as a submodule: `git submodule add <url> submodules/<org>/<name>`

1. Build container image: `make container-build` (or `make container-all` for all Fedora versions)

1. Create virtualenv if not exist: `make setup-venv`

1. Execute
   `. .venv/bin/activate && python3 scripts/scaffold-package.py <name>`
   with your package instead of `<name>`

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
   make pkg-full-cycle PKG=<name> FEDORA_VERSION=43 COPR_REPO=nett00n/hyprland
   # Default variable values:
   # FEDORA_VERSION=43
   # PKG= (or PACKAGE=) — all packages if unset
   # COPR_REPO= — no push to Copr if unset
   ```

1. This would execute spec generation to `packages/<name>/<name>.spec`,
   srpm creation and local build

1. Check build logs in `logs/`

1. If the build failed, analyze logs for actionable errors:

   ```shell
   make pkg-log-analysis PKG=<name>
   ```

   This parses mock/srpm logs and reports:
   - Missing dependencies and suggested packages
   - Incompatible plugins (internal header errors)
   - Missing source files (broken submodules)
   - Other compile errors with line references

1. Fix issues in `packages.yaml` (add `build_requires`, exclude incompatible plugins, etc.) and retry

1. If anything new happened, make a report in `docs/errs/` using `_template.md`

1. Verify with rpmlint:

```shell
rpmlint packages/<name>/<name>.spec
```

13. Commit, make PR

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
python3 scripts/gen-vendor-tarball.py <name>
```

### Shared Libraries (`scripts/lib/`)

- **cache.py** — input hash computation for caching and build invalidation
- **deps.py** — dependency graph inference from `depends_on` and `build_requires`
- **detection.py** — license and Meson dependency detection from build files
- **gitmodules.py** — `.gitmodules` parsing, submodule commit/tag info extraction, and changelog generation
- **jinja_utils.py** — Jinja2 environment setup
- **log_analysis.py** — parsing mock/srpm logs for failure reporting
- **migration.py** — schema migration from old to new YAML format
- **paths.py** — canonical path constants (`SOURCES_DIR`, `BUILD_STATUS_YAML`, etc.) and helpers (`mock_chroot()`)
- **reporting.py** — build status printing and badge generation
- **rpm_macros.py** — RPM macro path normalization (e.g., `/usr/bin/foo` → `%{_bindir}/foo`)
- **subprocess_utils.py** — subprocess wrappers (`run_cmd`, `run_git`)
- **tarball.py** — tarball source name detection via streaming curl|tar
- **vendor.py** — Go vendor tarball generation
- **version.py** — semantic version parsing and selection
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
make setup-venv   # creates .venv and installs requirements-dev.txt (mypy, ruff, yamllint, flake8, rpmlint)
make container-build   # build container image for Fedora 43 (or FEDORA_VERSION=X for specific version)
```

### Running checks and formatting

```shell
# Run all linters (inside container, installs dev tools on first run)
make lint    # ruff check + flake8 + mypy + rpmlint + yamllint

# Format code
make ruff-format   # format Python scripts
make fmt           # complete formatting: ruff + path normalization + YAML sorting

# Pre-commit workflow: run all checks + formatting
make pre-commit QUIET=true   # add QUIET=true for concise output
```

**What each checker does:**

- **ruff** — fast Python linter and formatter
- **flake8** — style checker for Python
- **mypy** — static type checker for Python
- **rpmlint** — RPM spec linter
- **yamllint** — validates YAML files (packages.yaml, etc.)

All checks automatically exclude `submodules/` directory.

## Local Build Workflow

Prerequisites: a container image built with `make container-build`, and a Python venv:

```shell
make setup-venv   # one-time: creates .venv and installs requirements-dev.txt
make container-build   # one-time: build container image for Fedora 43
```

```shell
# Regenerate all spec files
make pkg-spec

# Download sources, build SRPM, test with mock
make pkg-mock PACKAGE=<name> FEDORA_VERSION=43
```

### Full Cycle Pipeline Options

The `pkg-full-cycle` target supports several flags:

```shell
# Default: build spec → vendor → srpm → mock → copr (if COPR_REPO set)
make pkg-full-cycle PACKAGE=<name> FEDORA_VERSION=43

# Resume from interrupted run (skip already-succeeded stages)
make pkg-full-cycle PACKAGE=<name> PROCEED_BUILD=true

# Skip mock stage (stop after srpm, useful for quick validation)
make pkg-full-cycle PACKAGE=<name> SKIP_MOCK=true

# Skip copr submission (test locally without pushing)
make pkg-full-cycle PACKAGE=<name> SKIP_COPR=true

# Combine options
make pkg-full-cycle PACKAGE=<name> SKIP_MOCK=true FEDORA_VERSION=42
```

### Build Cache and Force Re-run

By default, `pkg-full-cycle` skips stages whose inputs haven't changed (hash-based caching).
To force a stage to re-run, edit `build-report.yaml` and set `force_run: true`:

```yaml
stages:
  spec:
    hyprland:
      state: success
      force_run: true    # operator sets to force re-execution
      version: "0.45.2-1.fc43"
      # ... rest of entry
```

**Rules:**
- Setting `force_run: true` on any stage forces that stage and all downstream stages to re-run
  (intra-package cascade: spec → vendor → srpm → mock → copr)
- If any package in `depends_on` was rebuilt in the current run, all stages of the dependent
  package are forced (inter-package dependency cascade)
- After a stage executes (success or fail), the `force_run` field is automatically removed
  (operator must re-set to force again; one-shot behavior)

### Build Report Backups

At the start of each `pkg-full-cycle` run, the existing `build-report.yaml` is automatically backed up
with an RFC 3339 timestamp (filesystem-safe): `build-report.2026-03-21T10-30-45+00-00.yaml`.
This happens before any processing begins, preserving the previous state and allowing rollback if needed.

### Running individual pipeline stages

```shell
# Run stages individually (each reads/writes build-report.yaml)
make stage-validate PKG=<name>   # validate packages.yaml (required fields, conventions)
make stage-spec     PKG=<name>
make stage-vendor   PKG=<name>   # Go packages only: generates vendor tarball
make stage-srpm     PKG=<name>
make stage-mock     PKG=<name>
make stage-copr     PKG=<name> COPR_REPO=nett00n/hyprland

# Compose a custom pipeline (e.g. skip copr)
make stage-validate stage-spec stage-vendor stage-srpm stage-mock PKG=<name>
```

`PACKAGE` (or `PKG`) is matched case-insensitively, so `PACKAGE=hyprland` and `PACKAGE=Hyprland` both work.

When `PACKAGE` is set, `pkg-full-cycle` automatically includes transitive build dependencies and processes them in topological order.

## Submitting to Copr

```shell
export COPR_REPO=nett00n/hyprland-extras
make pkg-copr PACKAGE=<name>
```

Requires `copr-cli` configured with `~/.config/copr`.

## Checklist Before Opening a PR

- [ ] `packages.yaml` entry is complete and correct
- [ ] `make stage-validate PACKAGE=<name>` passes with no errors
- [ ] `rpmlint` passes with no errors
- [ ] Builds cleanly with `make pkg-mock PKG=<name>`
- [ ] `Source0:` points to an upstream release tarball (not a manual archive) and uses `#/%{name}-%{version}.tar.gz` suffix to avoid filename collisions between packages at the same version
- [ ] No bundled C/C++ libraries (Go vendor tarballs are acceptable)
- [ ] Changelog entry added with correct date and your name
