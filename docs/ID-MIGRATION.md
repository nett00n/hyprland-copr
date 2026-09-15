# ID migration — DDD adoption (2026-09-15)

One-time renumbering performed when `docs/` was brought in line with
`docs/DOCS-DRIVEN-DEVELOPMENT.md`. `docs/TODO.md` previously held both new-feature
ideas and shipped-behavior defect/debt/chore items; DDD reserves `TODO.md` for the
former only, so every debt/chore/defect entry moved into `docs/BUGS.md` under one of
its three mandatory sections, and every substantial not-yet-built feature was promoted
into a `Planned` doc under `docs/features/`.

**Old `TODO-NNNN` IDs below are dead** — they no longer appear anywhere except this
table and `docs/CHANGELOG.md` history (which is left as originally written). Any
comment, commit message, or old branch still citing one of these should be read via
this table.

Entries not listed here (`TODO-0008`, `TODO-0009`, `TODO-0010`, `TODO-0011`,
`TODO-0013`, `TODO-0022`, `TODO-0023`, `TODO-0024`, `TODO-0025`, `TODO-0027`,
`TODO-0028`, `TODO-0066`, `TODO-0070`, `TODO-0071`, `TODO-0074`, `TODO-0085`,
`TODO-0088`) either kept their ID (small ideas still in `TODO.md`) or were promoted to
a feature doc (see the "→ feature" column below) rather than renumbered.

## Migrated to `docs/BUGS.md`

| Old ID | New ID | Section |
| --- | --- | --- |
| TODO-0073 | BUG-0057 | Bugs & quirks |
| TODO-0076 | BUG-0058 | Tech debt |
| TODO-0015 | BUG-0059 | Tech debt |
| TODO-0017 | BUG-0060 | Chores |
| TODO-0018 | BUG-0061 | Tech debt |
| TODO-0020 | BUG-0062 | Tech debt |
| TODO-0087 | BUG-0063 | Tech debt |
| TODO-0077 | BUG-0064 | Bugs & quirks |
| TODO-0026 | BUG-0065 | Tech debt |
| TODO-0030 | BUG-0066 | Tech debt |
| TODO-0086 | BUG-0067 | Tech debt |
| TODO-0031 | BUG-0068 | Chores |
| TODO-0032 | BUG-0069 | Tech debt |
| TODO-0033 | BUG-0070 | Tech debt |
| TODO-0035 | BUG-0071 | Bugs & quirks |
| TODO-0089 | BUG-0072 | Bugs & quirks |
| TODO-0078 | BUG-0073 | Chores |
| TODO-0036 | BUG-0074 | Chores |
| TODO-0038 | BUG-0075 | Chores |
| TODO-0039 | BUG-0076 | Tech debt |
| TODO-0040 | BUG-0077 | Tech debt |
| TODO-0041 | BUG-0078 | Tech debt |
| TODO-0090 | BUG-0079 | Bugs & quirks |
| TODO-0093 | BUG-0080 | Bugs & quirks |
| TODO-0091 | BUG-0081 | Chores |
| TODO-0092 | BUG-0082 | Bugs & quirks |
| TODO-0042 | BUG-0083 | Tech debt |
| TODO-0043 | BUG-0084 | Tech debt |
| TODO-0045 | BUG-0085 | Chores |
| TODO-0046 | BUG-0086 | Chores |
| TODO-0049 | BUG-0087 | Tech debt |
| TODO-0050 | BUG-0088 | Chores |
| TODO-0052 | BUG-0089 | Bugs & quirks |
| TODO-0056 | BUG-0090 | Chores |
| TODO-0057 | BUG-0091 | Tech debt |
| TODO-0058 | BUG-0092 | Bugs & quirks |
| TODO-0079 | BUG-0093 | Tech debt |
| TODO-0080 | BUG-0094 | Tech debt |
| TODO-0081 | BUG-0095 | Tech debt |
| TODO-0082 | BUG-0096 | Chores |
| TODO-0083 | BUG-0097 | Bugs & quirks |
| TODO-0062 | BUG-0098 | Tech debt |
| TODO-0063 | BUG-0099 | Bugs & quirks |
| TODO-0068 | BUG-0100 | Bugs & quirks |
| TODO-0075 | BUG-0101 | Tech debt |
| TODO-0069 | BUG-0102 | Chores |

New (not migrated from an old ID): **BUG-0103** — apply DDD's `#COPR-NNNN` comment
convention to every top-level function that implements a feature (out of scope for the
DDD-adoption change itself; filed as a chore so it isn't forgotten).

## Promoted to `docs/features/` (Planned)

| New feature | Absorbed TODO entries |
| --- | --- |
| [COPR-0019](features/COPR-0019-build-target.md) | TODO-0022, TODO-0023, TODO-0025, TODO-0085 |
| [COPR-0020](features/COPR-0020-aarch64-local-builds.md) | TODO-0008, TODO-0024 |
| [COPR-0021](features/COPR-0021-copr-chroot-matrix.md) | TODO-0009, TODO-0027, TODO-0028 |
| [COPR-0022](features/COPR-0022-run-scoped-logs-and-summary.md) | TODO-0066, TODO-0074, TODO-0088 |
| [COPR-0023](features/COPR-0023-source-signature-verification.md) | TODO-0070, TODO-0071 |

Next free ID after this migration: **BUG-0104**.
