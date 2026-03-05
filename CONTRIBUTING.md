# Contributing

## Repository Layout

```
packages.yaml                      # single source of truth — metadata for all packages
packages/<name>/<name>.spec        # generated spec files (committed, editable)
templates/spec.j2                  # Jinja2 spec template
templates/readme-github.md.j2      # Jinja2 template for GitHub README (table format)
templates/readme-copr.md.j2        # Jinja2 template for COPR README (list format)
templates/packages-entry.yaml.j2   # Jinja2 template for new packages.yaml entries
scripts/gen-spec.py                # renders specs from packages.yaml + templates/spec.j2
scripts/gen-report.py              # renders the build report from build-report.yaml
scripts/gen-vendor-tarball.py      # standalone: generate Go vendor tarball for one package
scripts/stage-spec.py              # pipeline stage: generate spec files
scripts/stage-vendor.py            # pipeline stage: generate Go vendor tarballs
scripts/stage-srpm.py              # pipeline stage: build SRPMs
scripts/stage-mock.py              # pipeline stage: local mock build
scripts/stage-copr.py              # pipeline stage: submit to Copr
scripts/lib/                       # shared library modules for all scripts
requirements.txt                   # Python deps (jinja2, pyyaml)
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
2. `make container-all` would create toolbox environment for compilation
3. Create virtualenv if not exist: `make setup-venv`
4. Execute
  `. .venv/bin/activate && python3 scripts/scaffold-package.py <name>`
  with your package instead of `<name>`
5. New entry would be added to `packages.yaml`:
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
          - url: "%{url}/archive/refs/tags/v%{version}.tar.gz"
        build_system: cmake  # cmake | meson | autotools | make
        build_requires:
          - cmake
          - pkgconfig(wayland-client)
        files:
          - "%license LICENSE"
          - "%{_bindir}/<name>"
    ```
6. Update FIXME fields with your ones
7. Start build cycle:
    ```shell
    make pkg-full-cycle PKG=<name> FEDORA_VERSION=43 COPR_REPO=nett00n/hyprland
    # Default variable values:
    # FEDORA_VERSION=43
    # PKG= (or PACKAGE=) — all packages if unset
    # COPR_REPO= — no push to Copr if unset
    ```
8. This would execute spec generation to `packages/<name>/<name>.spec`,
  srpm creation and local build
9. Check build logs in `logs/`
10. If the build failed, fix and retry
11. If anything new happened, make a report in `docs/errs/` using `_template.md`
12. Verify with rpmlint:
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
  - url: "%{url}/archive/refs/tags/v%{version}.tar.gz"
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

## Local Build Workflow

Prerequisites: a toolbox container built with `make container-build`, and a Python venv:

```shell
make setup-venv   # one-time: creates .venv and installs jinja2 + pyyaml
```

```shell
# Regenerate all spec files
make pkg-spec

# Download sources, build SRPM, test with mock
make pkg-mock PACKAGE=<name> FEDORA_VERSION=43
```

### Running individual pipeline stages

```shell
# Run stages individually (each reads/writes logs/build-status.yaml)
make stage-spec   PKG=<name>
make stage-vendor PKG=<name>   # Go packages only: generates vendor tarball
make stage-srpm   PKG=<name>
make stage-mock   PKG=<name>
make stage-copr   PKG=<name> COPR_REPO=nett00n/hyprland

# Compose a custom pipeline (e.g. skip copr)
make stage-spec stage-vendor stage-srpm stage-mock PKG=<name>
```

## Submitting to Copr

```shell
export COPR_REPO=nett00n/hyprland-extras
make pkg-copr PACKAGE=<name>
```

Requires `copr-cli` configured with `~/.config/copr`.

## Checklist Before Opening a PR

- [ ] `packages.yaml` entry is complete and correct
- [ ] `rpmlint` passes with no errors
- [ ] Builds cleanly with `make pkg-mock PKG=<name>`
- [ ] `Source0:` points to an upstream release tarball (not a manual archive)
- [ ] No bundled C/C++ libraries (Go vendor tarballs are acceptable)
- [ ] Changelog entry added with correct date and your name
