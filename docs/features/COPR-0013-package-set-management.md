# COPR-0013. Manage the package set

**Tags:** #packages #maintenance

## User Story

As a maintainer, I want to list upstream tags, lock a release, delete a package
cleanly, or reset build status without hand-editing `packages.yaml` and
`build-report.db` in sync, so that routine package-set maintenance stays a single
command.

## Behavior

| Command | Does |
| --- | --- |
| `make list-tags PACKAGE=<name>` | list upstream tags, highlighting latest semver |
| `make set-release PACKAGE=<name> RELEASE=<n> [LOCK=1]` | set (and optionally lock) a release |
| `make delete-package PACKAGE=<name>` | remove from `packages.yaml`, `groups.yaml`, `sources.lock.yaml`, `build-report.db`, `logs/build`, `packages/`, submodules, container rpmbuild dirs |

## Implementation

- `scripts/list-tags.py`, `scripts/set-package-release.py`, `scripts/delete-package.py`.
- `delete-package.py` cleans the `build_db.forget_package` artifacts ledger.

## Quirks & Decisions

- Quirk: `delete-package.py` cleans the artifacts ledger but never touches
  `local-repo/*/<pkg>-*.rpm` — stale RPMs linger across every target with no DB row
  pointing at them anymore, worse off than before the ledger cleanup existed.
  Proposed: glob-and-unlink plus `regenerate_repo_metadata` per touched target.
  (BUG-0071)
- Quirk: `delete-package` still holds submodule surgery and the volume sweep directly
  in the Makefile recipe after its script call, untestable by pytest.
  Proposed: move into `scripts/*.py`, same as [COPR-0001](COPR-0001-add-package-from-url.md)'s
  quirk about `add-submodule`/`add-new`. (BUG-0070)
- Quirk: `set-package-release.py`'s `--lock` is detected by `"--lock" in sys.argv`, so
  `set-package-release.py --lock <name> <release>` silently treats `--lock` as the
  package-name positional instead of erroring.
  Proposed: real flag parsing (argparse, or filter `--lock` out of positionals before
  indexing). (BUG-0082)

## Testing

### Unit

- `tests/test_set_package_release.py`, `tests/test_db_artifacts.py`.

## Status

Implemented
