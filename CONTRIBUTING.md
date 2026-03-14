# Contributing

## Repository Layout

```
packages.yaml                      # single source of truth — metadata for all packages
packages/<name>/<name>.spec        # generated spec files (committed, editable)
templates/spec.j2                  # Jinja2 spec template
templates/readme-github.md.j2      # Jinja2 template for GitHub README (table format)
templates/readme-copr.md.j2        # Jinja2 template for COPR README (list format)
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
requirements-dev.txt               # Python deps (jinja2, pyyaml, mypy, ruff, yamllint, mdformat)
submodules/<org>/<name>/           # upstream sources as git submodules
```

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

1. `make container-all` would create toolbox environment for compilation

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
       source_name: <name>  # omit if tarball top-level dir matches "<name>-<version>"
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

1. If the build failed, fix and retry

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

## Code Quality and Linting

The repository uses multiple linters and formatters to maintain code quality. All checks run inside the toolbox container:

### Setup (one-time)

```shell
make setup-venv   # creates .venv and installs requirements-dev.txt (mypy, ruff, yamllint, mdformat)
```

### Running checks and formatting

```shell
# Run all linters (inside toolbox, installs dev tools on first run)
make lint    # ruff check + mypy + yamllint + mdformat

# Format code
make ruff-format   # format Python scripts
make fmt           # complete formatting: ruff + path normalization + YAML sorting

# Pre-commit workflow: run all checks + formatting
make pre-commit
```

**What each checker does:**

- **ruff** — fast Python linter and formatter
- **mypy** — static type checker for Python
- **yamllint** — validates YAML files (packages.yaml, etc.)
- **mdformat** — checks and formats Markdown files (README.md, docs/)

All checks automatically exclude `submodules/` directory.

## Local Build Workflow

Prerequisites: a toolbox container built with `make container-build`, and a Python venv:

```shell
make setup-venv   # one-time: creates .venv and installs requirements-dev.txt
```

```shell
# Regenerate all spec files
make pkg-spec

# Download sources, build SRPM, test with mock
make pkg-mock PACKAGE=<name> FEDORA_VERSION=43
```

Set `PROCEED_BUILD=true` to resume an interrupted run without rebuilding packages that
already succeeded in the current `build-report.yaml`:

```shell
toolbox run -c rpm43 env PROCEED_BUILD=true python3 scripts/full-cycle.py
```

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
