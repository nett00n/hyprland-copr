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
    release_type: latest-commit  # or: latest-version, latest-tag, pinned-version, pinned-commit, pinned-tag
    branch: dev                   # optional: override default branch
  url: https://github.com/org/repo
  version: "0.53.0"
```

| Type | Behavior | Extra fields | Version format |
|------|----------|--------------|---|
| `latest-version` | Latest semver tag only, no commit fallback | `branch` | `1.2.3` |
| `latest-tag` | Latest version-like tag (any component count, e.g. `1.9`), no commit fallback | `branch` | `1.9` |
| `latest-commit` | Latest commit on branch | `branch` | `1.2.3^20240101gitabc1234` |
| `pinned-version` | Pins the checkout to tag `v<version>` (or bare `<version>`); no updates | `version` | - |
| `pinned-commit` | Pins the checkout to `source.commit.full`; no updates | `commit` | - |
| `pinned-tag` | Pins the checkout to a specific non-semver tag | `tag` | `0.53.0^20240101gitabc1234` |
| *(absent)* | Default: try semver, fall back to commit | `branch` | `1.2.3` or `0^20240101gitabc1234` |

`release_type` must match one of the types above (or be absent) -- `make validate-packages` and
`make stage-validate` both reject anything else, rather than silently falling through to the
default resolution path.

For `latest-commit`/`pinned-tag`, versions use the nearest reachable semver tag as a prefix:
`0.53.0^20240101gitabc1234` (commit after `v0.53.0`) or `0^20240101gitabc1234` (no semver tag
reachable). When `source.commit` exists (archive-based sources), it's auto-populated with the
full hash and date.

`latest-tag` accepts an optional pre-release suffix (`2.0.0-rc1`), ranked below the same numeric
tag without one. RPM `Version` can't contain `-`, so a winning pre-release is written as
`2.0.0~rc1` -- which no longer matches the upstream tag string, breaking a `source.archives`
entry templated on `%{version}`. `update-versions.py` warns when this happens.

Run manually: `python3 scripts/update-versions.py`, then `git add packages.yaml && git commit`.
`make update-daily` runs this as its first step.

## Source verification

`sources.lock.yaml` (repo root, committed) pins a sha256 for every remote file a package's
`source.archives`/`source.bundled_deps` download — the tarball that ends up packed into the
SRPM. `make stage-srpm` (and the Go/Rust vendor download path) fail closed on anything
downloaded that has no entry, or whose hash no longer matches: a retagged upstream release, a
tampered mirror, or a truncated download all get caught before they reach a published RPM
(see `docs/bugs.md` BUG-0025).

After a version bump (`make update-versions`), record the new hash:

```console
make refresh-checksums PACKAGE=<name>
```

This is the *only* thing that writes `sources.lock.yaml` — review the diff before committing,
same as any other change. `make update-daily` runs it automatically between `update-versions`
and the build. `make check-checksums` (also run by `make sources`) verifies without downloading
or writing anything.

An existing entry whose filename is unchanged but whose hash differs is refused by default —
that's exactly the retag/tamper case this exists to catch. Only pass `FORCE_CHECKSUM=1` after
manually verifying *why* the bytes changed (e.g. confirming with upstream that a tag was
intentionally re-pushed); reflexively forcing defeats the point.

This is TOFU (trust-on-first-use): the lock proves a file's bytes haven't changed since the
hash was first recorded and reviewed in a diff, not that upstream was honest at record time.
It does not check GPG signatures — see `docs/todo.md` for that.

## Go vendoring

Add `golang` to `build_requires`. The vendor stage auto-generates
`<name>-<version>-vendor.tar.gz` into `~/rpmbuild/SOURCES/` before the SRPM is built — `go mod
vendor` pulls in all dependencies (including git sources), and Go checks `vendor/` first with no
extra config needed.

Before running `go mod vendor`/`cargo vendor`, the stage checks a content-addressed store at
`.cache/vendor/<pkg>/<input-hash>/` (`lib/vendor_store.py`). The hash covers the same inputs
every other stage's cache does (source URL, `go_subdir`/`rust_subdir`, patches, dependency
config) via `lib.cache.compute_input_hashes`, so a hit is reused verbatim and a miss rebuilds and
re-populates the store. Unlike `~/rpmbuild/SOURCES` (one podman volume per `FEDORA_VERSION`),
this store is shared across every target, so `make full-cycle-matrix` builds a given vendor tree
once instead of once per Fedora version. Entries are recorded in the `artifacts` table under
`realm="vendor-store"` and reclaimed by `make db-prune` like any other artifact.

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
Fedora/COPR convention. `stage-vendor` fails the vendor stage itself if `cargo vendor` produces
any crate without a registry checksum (`.cargo-checksum.json`'s `"package"` is `null`) — the
signature of a git/path source — rather than letting the build fail two stages later in the
offline mock chroot.

Vendoring always runs against a downloaded, hash-pinned tarball in a scratch tmpdir — it never
touches `submodules/`, for either language.

`make stage-mock` disables `rpmbuild_networking`/`use_host_resolv` for the local chroot, so an
incomplete vendor tree fails locally instead of only on COPR.

`stage-vendor` also fails loud on toolchain skew: a `go.mod` `toolchain` directive or a
`Cargo.toml` `rust-version` is compared (via `dnf repoquery`) against what the target Fedora
release would actually install into the mock chroot, since vendoring runs against the
container's own `go`/`cargo`, not the chroot's.

If an upstream `Cargo.lock` pins a crate version that's broken against the vendoring
toolchain (e.g. a rustc type-inference regression the crate later fixed), bump it before
`cargo vendor` runs:

```yaml
build:
  cargo_update:
  - time@0.3.34
```

Each entry is passed as `cargo update -p <spec>` (pkgid syntax disambiguates when more than
one version of the crate is in the tree). No `--precise` — it resolves to the latest
semver-compatible version at vendor-generation time, so it stays self-healing as crates.io
publishes further fixes; a first-generation vendor tarball is then cached in the
content-addressed vendor store like any other, so this doesn't compromise reproducibility
between cache hits.

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
