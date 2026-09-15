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

## Implementation

- `scripts/gen-report.py` (`--format github|copr|full-report`, `--output`, both
  repeatable and paired positionally).
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
- Quirk: nothing verifies the generated docs body (packages table + build status)
  still matches `packages.yaml`/`build-report.db` — `make readme` needs
  `build-report.db`, which is gitignored, so CI has no build history to render from.
  Open: needs a design decision (commit a report snapshot? skip the Copr-dependent
  parts of a diff check?) — a `make db-export` snapshot (BUG-0060) is the natural
  input once it exists. (BUG-0031)

## Testing

### Unit

- `tests/test_gen_report.py`, `tests/test_readme_content.py`.

## Status

Implemented
