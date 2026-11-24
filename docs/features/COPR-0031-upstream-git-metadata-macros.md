# COPR-0031. Upstream git metadata macros for tarball builds

**Tags:** #packaging #spec #upstream

## User Story

As a maintainer, I want projects that stamp their binary from git (`Hyprland --version`)
to show the real commit message and commit count even though we build from a release
tarball with no `.git`, so that the version output is complete and `hyprpm`/bug reports
are not full of `unknown`.

## Behavior

When the upstream mirror resolves the package's tag (or `source.commit.full`), `make
stage-spec` emits two RPM globals next to `%global commit`:

```
%global upstream_commit_subject <first line of the tagged commit message>
%global upstream_commits <git rev-list --count of the tagged commit>
```

A package uses them from `build.commands`, for example Hyprland:

```yaml
- export GIT_BRANCH=v%{version}
- export GIT_COMMIT_MESSAGE="%{?upstream_commit_subject}"
- export GIT_COMMITS=%{?upstream_commits}
```

The commit date is not a macro: it is read from the source tarball at build time, because
`git archive` stamps every entry with the commit time, so it is correct even if the
generated spec is stale. See "Git metadata for builds from release tarballs" in
`docs/packaging.md`.

The subject is sanitized before it is written: `%` becomes `%%`, `"` becomes `'`,
backslashes and control characters are dropped. Upstream pastes it unescaped into a C
string (`version.h.in`) and it must survive `%global` and shell expansion.

Without a mirror (or when the tag is not found) neither macro is emitted. Packages
reference them as `%{?name}`, so they expand to nothing and upstream falls back to its own
`unknown` / `0`.

## Implementation

- `scripts/lib/upstream.py`: `get_commit_meta` reads the subject and commit count;
  `get_changelog_info` merges them (`subject`, `commits`) into the tag/commit info.
- `scripts/stage-spec.py`: builds the sanitized values from the changelog info.
- `templates/spec.j2`: renders the globals.
- `packages.yaml`: the `Hyprland` entry's `build.commands`.

## Quirks & Decisions

- Decision: branch is the tag name (`v%{version}`). A tag build has no honest branch;
  upstream cuts patch releases from `v<version>-b`, not `main`.
- Decision: `Libraries: ... system has unknown` is not fixed here. Hyprland reads
  `<lib>.pc` from `/usr/lib64/pkgconfig` at runtime; those files ship only in the
  `*-devel` packages, so it reads `unknown` until they are installed.

## Testing

### Unit

- `tests/test_upstream.py` — `get_commit_meta` on a real temp repo; `get_changelog_info` merges it.
- `tests/test_git_metadata_macros.py` — globals rendered, sanitized, omitted without info.
- `tests/test_hyprland_commit_env.py` — the Hyprland exports precede `%cmake`.

### Manual

- `make full-cycle PACKAGE=Hyprland`, install the RPM, run `Hyprland --version`.

## Status

In progress
