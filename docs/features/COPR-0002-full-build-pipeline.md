# COPR-0002. Full build pipeline (spec → vendor → srpm → mock → copr)

**Tags:** #build #pipeline #copr

## User Story

As a maintainer building one or all packages, I want a single command that runs every
pipeline stage in order, skipping what's already up to date, so that I don't have to
run each stage by hand or rebuild unchanged packages.

## Behavior

```mermaid
flowchart LR
  V[validate] --> S[spec] --> D[vendor] --> R[srpm] --> M[mock] --> C[copr]
```

`make full-cycle PACKAGE=<name> FEDORA_VERSION=43` runs validate → spec → vendor (Go/
Rust only, no-op otherwise) → srpm → mock → copr for one package or all packages
(`PACKAGE` unset). `PACKAGE`/`PKG` is case-insensitive; when set, transitive
`depends_on` dependencies are pulled in and topologically ordered automatically.

Each stage is individually skippable/forceable and cached by content hash, so an
unchanged package is skipped on rerun. Flags: `PROCEED_BUILD=true` (resume, skip
already-succeeded stages), `SKIP_MOCK=true`/`SKIP_COPR=true`, `SYNCHRONOUS_COPR_BUILD=
true` (wait for Copr instead of `--nowait`), `REQUIRE_CHROOT_COVERAGE=true`,
`FORCE_REBUILD=1` (ignore cache).

The `mock` stage's cache check also verifies that every (non-skipped) transitive
dependency's own `mock`-stage artifact still exists in `local-repo/<target>/` — not
just the package's own artifact. A dependency's RPM going missing there (stale-
artifact prune, a partial `clean-localrepo`, volume corruption) invalidates every
package that (transitively) depends on it, with reason `dep-artifact-missing: <dep>`,
rather than silently staying "cached" (#BUG-0064).

| Stage | What it does |
| --- | --- |
| validate | packages.yaml entry + `.gitmodules` sanity |
| spec | render `packages/<name>/<name>.spec` from `templates/spec.j2` |
| vendor | Go/Rust dependency tarball (no-op for other build systems) |
| srpm | download sources, verify checksums, build the SRPM |
| mock | local test build in the target chroot |
| copr | submit to Copr, gated per package (see COPR-0007) |

## Implementation

- `scripts/full-cycle.py`'s `run_build_pipeline()` orchestrates the six stages via
  the matching `scripts/stage-*.py` modules.
- Caching: `lib/cache.py` (`compute_input_hashes`/`hashes_match`) + `lib/pipeline.py`
  (`is_cached()`), backed by `build-report.db` (see COPR-0015).
  `compute_input_hashes()`'s dict has one key per cache input: `source_commit`,
  `templates`, `generator`, `content` (the package config minus `release`),
  `dependencies`, `patches`, `package_version`. `content` is the single
  implementation for "package config hash" — a prior duplicate under the key
  `package_config` (byte-identical to `content`, stored twice in every stage row)
  was removed (#BUG-0098); reading an old row's stored `hashes` therefore always
  misses once, which is why this rides along with a migration that costs a full
  rebuild anyway rather than paying for a cache-wide miss twice.
  `templates`/`generator` are *advisory*: `hashes_match()` only compares the
  remaining ("invalidating") keys, so editing `spec.j2` or the generator itself
  never forces a rebuild — `lib.cache.stale_advisories()` reports which packages'
  cached spec is now stale instead (#BUG-0057, #BUG-0058; see COPR-0005).
- Standalone equivalents exist per stage: `make stage-validate`/`stage-spec`/
  `stage-vendor`/`stage-srpm`/`stage-mock`/`stage-copr PACKAGE=<name>`.

## Quirks & Decisions

- Quirk: `run_build_pipeline()` (`full-cycle.py:267-691`) is 425 lines of repeated
  per-stage orchestration — cache check → `run_for_package()` → `build_db.finalize_stage()`
  — the same shape six times.
  Proposed: a small stage-runner abstraction; do together with the per-stage
  "config: skip" copy-paste (six `set_stage()` call sites). (BUG-0076, BUG-0077)
- Quirk: an edit to `spec.j2` invalidates all packages' caches at once via a strict
  full-dict hash comparison, forcing a full rebuild.
  Proposed: report "spec generated from an outdated template" instead of forcing a
  rebuild. (BUG-0057)

## Testing

### Unit

- `tests/test_cache_and_yaml_utils.py`, `tests/test_cache_gaps.py`,
  `tests/test_pipeline_copr_stage_utils.py`.

### Integration

- `tests/integration/test_cache_pipeline.py`, `tests/integration/test_make_targets.py`,
  `tests/integration/test_entry_points.py`.

## Status

Implemented
