# packages.yaml reference

`packages.yaml` is the single source of truth for every package. This doc covers the schema
extras beyond what's in the "Adding a New Package" example in `docs/CONTRIBUTING.md`.

## Groups

Top-level `groups` section controls how packages are bucketed in the generated build report. A
package can belong to multiple groups; packages in none still appear in the raw list but are
omitted from the grouped report.

```yaml
groups:
  hyprland:
    label: "Hyprland main packages"
    packages:
      - Hyprland
      - hypridle
```

## Version auto-updates

`auto_update` controls how `scripts/update-versions.py` (via `make update-versions`) bumps a
package's version. Config and resolved versions are keyed by **package name**, not `url` — two
packages can share a `url` (e.g. a stable package and its `-git` sibling) and each gets its own
`auto_update.release_type` applied independently. `make stage-validate` warns if two packages
share a `url`, as a nudge to double-check both have the config they need.

```yaml
package-name:
  auto_update:
    release_type: latest-commit  # or: latest-version, pinned-version, pinned-commit, pinned-tag
    branch: dev                   # optional: override default branch
  url: https://github.com/org/repo
  version: "0.53.0"
```

| Type | Behavior | Extra fields | Version format |
|------|----------|--------------|---|
| `latest-version` | Latest semver tag only, no commit fallback | `branch` | `1.2.3` |
| `latest-commit` | Latest commit on branch | `branch` | `1.2.3^20240101gitabc1234` |
| `pinned-version` | Pins the checkout to tag `v<version>` (or bare `<version>`); no updates | `version` | - |
| `pinned-commit` | Pins the checkout to `source.commit.full`; no updates | `commit` | - |
| `pinned-tag` | Pins the checkout to a specific non-semver tag | `tag` | `0.53.0^20240101gitabc1234` |
| *(absent)* | Default: try semver, fall back to commit | `branch` | `1.2.3` or `0^20240101gitabc1234` |

For `latest-commit`/`pinned-tag`, versions use the nearest reachable semver tag as a prefix:
`0.53.0^20240101gitabc1234` (commit after `v0.53.0`) or `0^20240101gitabc1234` (no semver tag
reachable). When `source.commit` exists (archive-based sources), it's auto-populated with the
full hash and date.

Run manually: `python3 scripts/update-versions.py`, then `git add packages.yaml && git commit`.
`make update-daily` runs this as its first step.

## Go vendoring

Add `golang` to `build_requires`. The vendor stage auto-generates
`<name>-<version>-vendor.tar.gz` into `~/rpmbuild/SOURCES/` before the SRPM is built — `go mod
vendor` pulls in all dependencies (including git sources), and Go checks `vendor/` first with no
extra config needed.

If `go.mod` isn't at the tarball root (e.g. lives in `cli/`):

```yaml
go_subdir: cli
```

Then add the vendor tarball as `Source1` and extract it in `prep_commands`:

```yaml
sources:
  - url: "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
  - url: "%{name}-%{version}-vendor.tar.gz"
prep_commands:
  - "pushd cli"
  - "tar xf %{SOURCE1}"
  - "popd"
```

Manual generation: `make stage-vendor PACKAGE=<name>`.

## Rust vendoring

Add `cargo` to `build_requires` for pure crates.io dependencies — `stage-vendor` runs `cargo
vendor` the same way as Go. Packages with **git** crate dependencies (not resolvable offline)
instead build those dependencies as separate RPM packages and use system-installed crates, per
Fedora/COPR convention — see `docs/bugs.md` BUG-0021/BUG-0022 for the known rough edges in the
current implementation (submodule-path vendoring mutates the live checkout).

## Release auto-increment

Each package's RPM `release` is managed automatically by `full-cycle`'s pre-build step
(`update_package_releases()`):

1. Content hash (excludes `release` itself, so release-only edits don't trigger rebuilds) is
   compared against the stored hash from the last run.
2. **Version changed** → `release` resets to `1`.
3. **Content differs, same version** → `release` increments by 1.
4. **Content unchanged, no force_run, no dependency cascade** → no change.
5. **Force-run or a dependency was rebuilt** → `release` increments by 1, and cascades to every
   package that depends on it.

`update-versions.py` sets `release: 0` when it bumps a version (via `url_to_latest` or commit
info), signaling the next `full-cycle` to reset the counter to 1.

Manual override:

```shell
make set-release PACKAGE=my-package RELEASE=5            # set (still auto-increments on change)
make set-release PACKAGE=my-package RELEASE=5 LOCK=1      # set and lock (no auto-increment)
make set-release PACKAGE=pkg1,pkg2 RELEASE=10 LOCK=1       # comma-separated, multiple packages
```

`release_lock: true` in `packages.yaml` skips auto-management until the lock is removed.

## Template snippets (`templates/*.j2`)

Naming marks the include graph: `_*.j2` are leaf snippets with no includes (e.g. `_logo.j2`,
`_badge.j2`); `__*.j2` are composites that include other snippets (e.g. `__header.j2`,
`__footer.j2`). Keeps the composition graph readable and avoids circular includes.
