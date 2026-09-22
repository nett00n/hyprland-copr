# COPR-0012. Regenerate docs from the build-state source of truth

**Tags:** #docs #reporting

## User Story

As a maintainer, I want `README.md`, the Copr project readme, and the full build
report regenerated from `build-report.db`, so that published docs always reflect what
actually built rather than drifting from hand-edited text.

## Behavior

`make readme` renders `README.md`, `docs/README.copr.md`, and `docs/full-report.md`
from `build-report.db` in one container run and one Copr poll (not three). By default
it polls Copr for in-progress build status; the second and third render pass
`--skip-copr-poll` to avoid redundant API calls.

In `_update-daily`, `readme` now runs after `copr-wait` (see
[COPR-0007](COPR-0007-copr-submission.md)) has already bounded-retried the
just-submitted builds, so `copr-unknown` in the committed docs means "still
building at the poll deadline", not "not polled yet" (#BUG-0039).

`make check-docs-drift` (#BUG-0031) verifies the committed docs body still matches
their inputs: it re-renders `README.md`/`docs/README.copr.md`/`docs/full-report.md`
from `packages.yaml` + `docs/db-snapshot.yaml` (`gen-report.py --db-snapshot`) into a
scratch dir and diffs against the committed files, failing on any difference.
`docs/db-snapshot.yaml` (`make db-export-docs`) is a narrow, committed export of just
the latest `runs` row per target plus every `stage_results` row — the two tables
`gen-report.py` actually reads — kept in sync by `_update-daily` running it right
after `readme`. `--db-snapshot` implies no Copr poll (a snapshot has no live
`build_id`s to poll against), so the render is fully reproducible: two exports of an
unchanged db are byte-identical (`db-artifacts.py`'s `export_docs_snapshot()`).

## Implementation

- `scripts/gen-report.py` (`--format github|copr|full-report`, `--output`, both
  repeatable and paired positionally; `--db-snapshot PATH` for the drift-check
  render path).
- `scripts/db-artifacts.py --export-docs` / `lib.build_db.export_docs_snapshot()`,
  `stage_map_from_export()` (reshapes the snapshot's flat rows into `stage_map()`'s
  shape so `collect_packages()` has one code path for both the live and
  snapshot renders).
- `repo.yaml` controls branding/layout (badge style, News feed limit, per-section
  visibility) — package data itself always comes from `packages.yaml`/
  `build-report.db`.

## Quirks & Decisions

- Quirk: `{% if c.github_user %}...{% endif %}` in `_contributors.j2` is a block tag
  under `trim_blocks=True`, eating the newline after `{% endif %}` — contributor
  entries render concatenated on one line, no `-` before the second name. Compounded
  by `collect_contributors()` deduping by name only, so the same person committing
  under two `user.name` values renders as two entries. Masked in CI because
  `actions/checkout@v4`'s shallow clone only sees one git author; `repo.yaml`'s
  `sections.contributors: false` is a workaround, not a fix.
  Proposed: `{%- endif -%}` (or restructure without the inline `if`), plus dedupe by
  email instead of name. (BUG-0030)
- Decision (#BUG-0031): commit a *narrow* db snapshot (`docs/db-snapshot.yaml`,
  `runs`+`stage_results` only) rather than `db-export`'s full four-table dump —
  `stage_history`/`artifacts` are append-only and unbounded, and `gen-report.py`
  reads neither, so including them would grow the committed file for no reason a
  docs render needs.
- Quirk: `docs/db-snapshot.yaml` can only ever be as fresh as the last
  `make db-export-docs` (wired into `_update-daily` right after `readme`) — a
  manual `make readme` outside the nightly job, or a hand-edit of the generated
  docs, drifts the snapshot out of sync until the next `db-export-docs`. Not
  a design gap, just the tradeoff of not shipping `build-report.db` itself.

## Testing

### Unit

- `tests/test_gen_report.py` (incl. `TestGenReportDbSnapshot`),
  `tests/test_readme_content.py`, `tests/test_db_artifacts.py`
  (`TestExportDocsSnapshot`).

### Integration

- `make check-docs-drift`: negative control verified manually (hand-edited
  `docs/full-report.md`, confirmed the diff was caught and the target exits
  non-zero) — no automated test for the Makefile target itself, since it
  shells out to the real repo tree rather than a fixture.

## Status

Implemented
