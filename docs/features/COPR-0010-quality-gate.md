# COPR-0010. Local quality gate (validate, test, lint, format)

**Tags:** #ci #lint #testing #quality

## User Story

As a contributor, I want one command that validates, tests, lints, and formats the
repo the same way CI does, so that I catch a regression before opening a PR instead of
after.

## Behavior

| Command | Runs |
| --- | --- |
| `make validate-packages` | `packages.yaml`/`.gitmodules` sanity (fast, no container) |
| `make lint` | `lint-ruff` + `lint-flake` + `lint-mypy` + `lint-rpm` + `lint-yaml` |
| `make fmt` | `fmt-ruff` + `fmt-yaml` + `normalize-paths` + `sort-lists` |
| `make pre-commit` | `validate-packages` + `test` + `lint` + `fmt` (`COVERAGE=1` adds a coverage report) |

Run `make pre-commit` before and after any change. CI runs lint + test only, natively
via `NO_CONTAINER=1` (CI can't nest privileged containers) on every push/PR.
`make update-daily` deliberately does **not** run the full gate — just
`validate-packages` + `fmt` — so an unrelated `scripts/` lint regression never blocks
a nightly Copr publish.

`validate-packages` and the real build's `stage-validate` share one validator
(`lib.validation`), so a passing `validate-packages` implies `stage-validate` will
pass too.

`validate-packages` also enforces, as **errors**:

- No `#BUG-NNNN`/`#TODO-NNNN` ID is declared twice within `docs/BUGS.md` or
  `docs/TODO.md`, and no ID's prefix mismatches its file. (#BUG-0073)
- Every `packages.yaml` scalar matches the type table in `lib.validation.FIELD_TYPES`
  (a YAML float/bool where a string/int is expected is rejected, not silently
  coerced). (#BUG-0097)
- A package whose `build_requires` triggers vendoring (`golang`/`cargo`) declares a
  matching `*-vendor.tar.gz` `source.archives` entry, and vice versa; a hand-written
  `prep`'s `%{SOURCEn}` reference stays inside the declared `archives` range.
  (#BUG-0089)

... and, offline and degrading by design (skips silently rather than warning
whenever a submodule isn't initialized or its ref isn't resolvable locally, so CI
and fresh clones stay green), as **warnings**:

- A commit-tracked package (`latest-commit`/`pinned-commit`) whose
  `source.commit.date` is newer than a tag/version-pinned `depends_on` sibling's
  pinned tag date — possible API drift ahead of a pinned dependency. (#BUG-0056)
- A package's declared `build.system` whose marker file (`CMakeLists.txt`,
  `meson.build`, ...) is missing from its submodule's tagged/pinned-commit tree
  (read via `git ls-tree`, never the working tree) — upstream likely switched build
  systems; names the system it looks like instead. (#BUG-0105)

`ruff check scripts/` (`make lint-ruff`) additionally selects `B,RUF,SIM,PLW` beyond
the default `E,F` (see `ruff.toml`), catching real variable-lifetime bugs (redefined
loop variables, unused unpacked variables) alongside style. (#BUG-0096)

## Implementation

- `Makefile` `lint*`/`fmt*`/`pre-commit`/`validate-packages` targets.
- `scripts/validate-packages.py` (thin front-end over `lib.validation`),
  `scripts/stage-validate.py` (the real build's stage 0, same validator).
- `mypy.ini` enforces `disallow_untyped_defs`/`disallow_incomplete_defs`; two flags
  (`disallow_any_generics`, `warn_return_any`) are deliberately still off, each
  tracked by its own tech-debt entry.

## Quirks & Decisions

- Decision: `lib.validation.validate_tracker_ids()` greps `docs/BUGS.md`/
  `docs/TODO.md` for `^- #(BUG|TODO)-\d+` declarations and errors on any ID declared
  twice within a file or filed under the wrong file's prefix — the exact class of
  bug the 2026-08-18 grooming pass found and fixed by hand. (BUG-0073, closed)
- Decision: `ruff.toml` selects `B,RUF,SIM` plus the useful `PLW` subset (catches real
  variable-lifetime bugs, e.g. 8 `PLW2901` redefined-loop-name instances); leaves
  `PLR0912/0913/0915`/`N999` off, since they fire on already-tracked large files and
  the intentional `kebab-case.py` script names; leaves `PLW0603` off (fires only on
  `lib/build_db.py`'s deliberate module-level connection singleton) and `RUF100` off
  (its autofix would delete the `# noqa: E402` directives `make lint-flake` still
  needs in `scripts/delete-package.py`, since flake8 and ruff don't share a
  suppression namespace). (BUG-0096, closed)
- Decision: `lib.validation.FIELD_TYPES` is a dotted-path → type table covering every
  scalar `packages.yaml.example` documents; a present-but-wrong-typed field
  (`version: 1.9`, `release: true`) is an error, absence stays `REQUIRED_FIELDS`'
  job. The ~15 `str()` call-site wrappers this makes redundant are left in place —
  removing them is BUG-0093's job once the `TypedDict` work below lands. (BUG-0097,
  closed)
- All three top-level scripts that had zero tests now have unit tests
  (`tests/test_gather_requires.py`, `tests/test_list_tags.py`,
  `tests/test_gen_readme_shell.py`), each faking the network/subprocess boundary the
  same way other recently-covered scripts do. (BUG-0078, closed)
- Quirk: 134 bare `dict`/`list`/`tuple` annotations block mypy's
  `disallow_any_generics`; 17 `Any`-laundering returns block `warn_return_any`.
  Proposed: `TypedDict`/`Literal` aliases for the stage-results row, package metadata,
  and `compute_input_hashes()`'s dict, plus typed loader wrappers at YAML/JSON trust
  boundaries. (BUG-0093, BUG-0094, BUG-0095)
- Decision: `validate_build_system_drift()` checks only whether the *declared*
  system's own marker is present — not whether it's the *first* marker
  `detect_build_system()` would return — so a repo that ships both `meson.build`
  and `CMakeLists.txt` mid-migration is never a false positive. It resolves the ref
  to inspect the same way as `validate_dependency_drift()`: the version tag via
  `get_tag_info()`, falling back to `source.commit.hash` for commit-tracked
  packages. `lib.detection.BUILD_SYSTEM_MARKERS` (data) plus
  `lib.detection.matches_build_system()` (the one function that evaluates it) is
  the single source of truth both this and `detect_build_system()` (used at
  `scaffold-package.py` time) call — no second copy of the marker logic to drift
  out of sync. A marker entry that is itself a tuple means "all of these
  together" (autotools' `configure`+`Makefile.in` pairing, distinct from
  `configure.ac` alone). Warning-level rather than an error, same rationale as
  BUG-0056: a false positive must never block `make update-daily`'s nightly Copr
  publish. (BUG-0105)

## Testing

### Unit

- `tests/test_validate_packages_script.py`, `tests/test_validation_gaps.py`
  (covers `validate_tracker_ids`, `FIELD_TYPES`/`validate_field_types`,
  `validate_vendoring`, `validate_dependency_drift`, `validate_build_system_drift`).
- `tests/test_detection.py` (covers `BUILD_SYSTEM_MARKERS` staying in sync with
  `detect_build_system()`).
- `tests/test_gather_requires.py`, `tests/test_list_tags.py`,
  `tests/test_gen_readme_shell.py`.

### Integration

- `tests/integration/test_validation_pipeline.py`.

## Status

Implemented
