# COPR-0006. Test-build packages locally in mock

**Tags:** #build #mock #testing

## User Story

As a maintainer, I want to test-build a package in a real chroot before it ever
touches Copr, so that a broken build fails fast locally instead of burning a Copr
build slot and round-trip.

## Behavior

`make stage-mock PACKAGE=<name> FEDORA_VERSION=43` builds the SRPM in `mock -r
fedora-<version>-x86_64`, resolving `depends_on` packages against `local-repo/
<target>/` (an RPM built for one Fedora version can't be served into a different
version's buildroot). `rpmbuild_networking`/`use_host_resolv` are disabled, so an
incomplete vendor tree fails locally the same way it would offline on Copr.

Before invoking mock at all, a preflight check confirms every local dependency's RPM
is actually present in `local-repo/<target>/` at the right dist tag — failing in
seconds with an actionable message instead of a multi-minute dnf5 resolution failure.
`SKIP_REPO_PREFLIGHT=1` overrides it.

## Implementation

- `scripts/stage-mock.py`, `scripts/lib/repo_preflight.py`.
- Mock's buildroot cache (`/var/cache/mock`, `/var/lib/mock`) persists across `--rm`
  containers via `mock-cache-<ver>`/`mock-root-<ver>` podman volumes, so builds don't
  re-bootstrap the chroot from scratch every run.

## Quirks & Decisions

- Quirk: mock's three logs (`build.log`/`root.log`/`state.log`) are copied out of the
  podman-volume resultdir after the fact instead of bind-mounted, so they can't be
  tailed live; log dirs also lack a distro/version segment, so an f43 and f44 build of
  the same package overwrite each other's logs.
  Proposed: bind-mount mock's resultdir (cheap, independent fix); restructure log
  paths to `./logs/<distro>/<version>/<package>/` together with
  [COPR-0022](COPR-0022-run-scoped-logs-and-summary.md).
- Quirk (fixed, #COPR-0032): mock names its resultdir after the config's `root`, not
  after `-r <target>`. `fedora-46-x86_64.cfg` is a symlink to rawhide's, so mock wrote
  to `/var/lib/mock/fedora-rawhide-x86_64/result` while `update_local_repo()` and
  `copy_mock_results()` read `/var/lib/mock/fedora-46-x86_64/result` -- every f46 build
  "succeeded" with an empty local repo and its dependents failed preflight. `_mock_cmd`
  now passes `--resultdir /var/lib/mock/<target>/result` explicitly, so the path the
  pipeline reads is always the one mock writes, whatever the config's root is called.

## Testing

### Unit

- `tests/test_stage_mock.py`, `tests/test_repo_preflight.py`.

### Integration

- `tests/integration/test_entry_points.py`.

## Status

Implemented
