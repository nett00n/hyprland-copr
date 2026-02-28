# Contributing

## Repository Layout

```
packages.yaml                # single source of truth — metadata for all packages
packages/<name>/<name>.spec  # generated spec files (committed, editable)
templates/spec.j2            # Jinja2 spec template
scripts/gen-spec.py          # renders specs from packages.yaml + templates/spec.j2
requirements.txt             # Python deps (jinja2, pyyaml)
upstream/<name>/             # gitignored — local upstream clones
```

## Adding a New Package

1. add repository as a submodule, saving structure ./submodules/org/name
2. `make container-all` would create toolbox environment for compilation
3. Create virtualenv if not exist `python3 -m virtualenv .venv`
4. Execute
  `. .venv/bin/activate && scripts/list-submodule-tags add hyprwire`
  with yur package instead of hyprwire
5. New entry would be added to `packages.yaml`:
    ```yaml
    packages:
      <name>:
        version: "1.2.3"
        release: 1
        license: MIT
        summary: One-line description
        description: |
          Longer description.
        url: https://github.com/org/<name>
        sources:                          # auto-indexed: Source0, Source1, ...
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
    make pkg-full-cycle PKG=<name> FEDORA_VERSION=42 COPR_REPO=nett00n/hyprland
    # Default variables values:
    # FEDORA_VERSION=43
    # PKG= # all packages
    # COPR_REPO= # no push to copr
    ```
8. This would execute spec generation to `packages/<name>/<name>.spec`,
  srpm creation and local build
9. Check build logs in .logs/
10. IF Build was failed, GOTO
    ELSE GOTO 11
11. IF anything new happen, make a report how to fix in docs.errs, using `_template.md`
12. Verify with rpmlint:
   ```shell
   rpmlint packages/<name>/<name>.spec
   ```
13. Commit, make PR

## Local Build Workflow

Prerequisites: a toolbox container built with `make build create`, and a Python venv:

```shell
make venv   # one-time: creates .venv and installs jinja2 + pyyaml
```

```shell
# Regenerate all spec files
make gen-spec

# Download sources, build SRPM, test with mock
make mock-build PACKAGE=<name> FEDORA_VERSION=43
```

## Submitting to Copr

```shell
export COPR_REPO=nett00n/hyprland-extras
make copr PACKAGE=<name>
```

Requires `copr-cli` configured with `~/.config/copr`.

## Checklist Before Opening a PR

- [ ] `packages.yaml` entry is complete and correct
- [ ] `rpmlint` passes with no errors
- [ ] Builds cleanly with `make mock-build`
- [ ] `Source0:` points to an upstream release tarball (not a manual archive)
- [ ] No bundled libraries
- [ ] Changelog entry added with correct date and your name
