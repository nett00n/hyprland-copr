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

## Implementation

- `Makefile` `lint*`/`fmt*`/`pre-commit`/`validate-packages` targets.
- `scripts/validate-packages.py` (thin front-end over `lib.validation`),
  `scripts/stage-validate.py` (the real build's stage 0, same validator).
- `mypy.ini` enforces `disallow_untyped_defs`/`disallow_incomplete_defs`; two flags
  (`disallow_any_generics`, `warn_return_any`) are deliberately still off, each
  tracked by its own tech-debt entry.

## Quirks & Decisions

- Quirk: ruff runs with default rules only (`E,F`) — no `ruff.toml`.
  Proposed: select `B,RUF,SIM` plus the useful `PLW` subset (catches real
  variable-lifetime bugs, e.g. 8 `PLW2901` redefined-loop-name instances); leave
  `PLR0912/0913/0915`/`N999` off, since they fire on already-tracked large files and
  the intentional `kebab-case.py` script names. (BUG-0096)
- Quirk: no field→type table for `packages.yaml` scalars — `REQUIRED_FIELDS` checks
  presence only, so a YAML float like `version: 1.9` passed both validators until
  found by hand.
  Proposed: add a field→type table to `lib/validation.py`; should land before the
  `TypedDict` typing work below, which depends on it. (BUG-0097)
- Quirk: three top-level scripts have zero tests (`gather-requires.py`,
  `gen-readme-shell.py`, `list-tags.py`), violating the stated coverage rule.
  Proposed: add tests using a network/subprocess fake, same pattern as other
  recently-covered scripts. (BUG-0078)
- Quirk: 134 bare `dict`/`list`/`tuple` annotations block mypy's
  `disallow_any_generics`; 17 `Any`-laundering returns block `warn_return_any`.
  Proposed: `TypedDict`/`Literal` aliases for the stage-results row, package metadata,
  and `compute_input_hashes()`'s dict, plus typed loader wrappers at YAML/JSON trust
  boundaries. (BUG-0093, BUG-0094, BUG-0095)

## Testing

### Unit

- `tests/test_validate_packages_script.py`, `tests/test_validation_gaps.py`.

### Integration

- `tests/integration/test_validation_pipeline.py`.

## Status

Implemented
