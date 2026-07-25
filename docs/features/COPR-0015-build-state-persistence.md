# COPR-0015 — Build state persistence

As a maintainer, build state survives between runs and isn't recomputed from scratch each time.

`build-report.yaml` is the single source of truth for what's been built: every pipeline stage
reads and writes it, recording a content hash per stage so unchanged work is skipped (with
`force`/`reason` overrides available). It also holds release history, and is snapshotted to a
timestamped backup before each write. All generated docs (README, COPR readme, full report) are
rendered from this file, not recomputed from packages.
