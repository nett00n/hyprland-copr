# COPR-0015 — Build state persistence

As a maintainer, build state survives between runs and isn't recomputed from scratch each time.

`build-report.db` (sqlite) is the single source of truth for what's been built: every pipeline
stage reads and writes it, recording a content hash per `(package, stage, target)` row so
unchanged work is skipped (with `force_run`/`reason` overrides available) — `target` is the mock
chroot, so a second Fedora version doesn't overwrite the first. An `artifacts` table tracks every
SRPM/RPM/vendor tarball produced, for disk usage reporting and pruning. All generated docs
(README, COPR readme, full report) are rendered from this DB, not recomputed from packages.
