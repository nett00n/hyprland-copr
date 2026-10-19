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
| `make delete-package PACKAGE=<name>` | remove from `packages.yaml`, `groups.yaml`, `sources.lock.yaml`, `build-report.db`, `logs/runs/`, `local-repo/*/` RPMs (repo metadata regenerated), `packages/`, container rpmbuild dirs |

## Implementation

- `scripts/list-tags.py`, `scripts/set-package-release.py`, `scripts/delete-package.py`.
- `delete-package.py` owns all cleanup except the `packages/<name>` `rm -rf`, which stays
  in the Makefile recipe: it cleans the `build_db.forget_package` artifacts ledger, unlinks
  the package's RPMs from every `local-repo/<target>/` and runs `createrepo_c` on each
  touched target (`lib/local_repo.remove_package_rpms`), and sweeps the rpmbuild volume
  (`sweep_rpmbuild`).

## Quirks & Decisions

- Decision: RPMs (in `local-repo/` and `RPMS/`) are matched by their `%{SOURCERPM}`
  name, and `SOURCES/`/`SRPMS/` entries by `<name>-<digit>...`, never by a bare
  `<name>-*` glob -- that would make deleting `hyprland` also remove
  `hyprland-protocols` and `hyprland-plugins`.
- Decision: a cached mirror under `.cache/upstream` is left in place: it is disposable and
  shared by url. (The submodule surgery went away with the submodules.)

## Testing

### Unit

- `tests/test_set_package_release.py`, `tests/test_db_artifacts.py`.
- `tests/test_delete_package.py`: local-repo RPM removal per target (prefix-collision
  sibling survives, metadata regenerated only for touched targets), rpmbuild-volume
  sweep, summary line, already-clean exit.

## Status

Implemented
