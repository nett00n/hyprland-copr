"""Build pipeline orchestration utilities.

Provides helpers for:
- Computing which stages must be forced to run
- Determining if stages are cached and can be skipped
- Choosing the `reason` string recorded for a stage's cache outcome

Stamping run metadata after a stage executes (the old `inject_stage_meta`) is
now `lib.build_db.finalize_stage` -- it's a plain UPDATE, not orchestration.
"""

from pathlib import Path

from lib import build_db
from lib.cache import hashes_match

# Stage order for cascading force_run (all stages except validate, which has no cache).
STAGE_ORDER = build_db.STAGES[1:]

# Stages whose "success" means files must still be on disk, and the artifacts.kind
# rows (see lib.build_db's `artifacts` table) that record them. spec/validate produce
# no tracked artifact; copr's result lives on the COPR side, not locally.
_STAGE_ARTIFACT_KINDS = {"vendor": "vendor", "srpm": "srpm", "mock": "rpm"}


def artifacts_present(stage: str, pkg: str, target: str, version: str | None) -> bool:
    """Check that every artifact recorded for this stage's success is still on disk.

    Stages not in `_STAGE_ARTIFACT_KINDS` (spec, copr) always return True -- they
    have no tracked artifact to verify. For the rest, at least one artifacts row
    must exist for (pkg, target, kind) at the exact `version` (NVR) the stage row
    recorded, and every matching row's path must still exist on disk.

    Version-scoped deliberately: stage-mock.py's prune_local_repo() deletes
    stale-NVR RPMs from local-repo/ without deleting their artifacts rows, so
    dangling rows for older NVRs are normal and must not satisfy this check --
    that's exactly the shape of the bug this guards against (see docs/bugs.md
    BUG-0015: a stage stayed "cached" while the current version's file was gone).
    """
    kind = _STAGE_ARTIFACT_KINDS.get(stage)
    if kind is None:
        return True
    rows = [
        row
        for row in build_db.artifacts(package=pkg, target=target, kind=kind)
        if row.get("version") == version
    ]
    if not rows:
        return False
    return all(Path(row["path"]).exists() for row in rows)


def compute_forced_stages(
    pkg: str,
    deps: set[str],
    target: str,
    rebuilt_packages: set[str],
    *,
    force_all: bool = False,
) -> set[str]:
    """Compute set of stages that must run due to force_run or dependency cascade.

    Rules:
    1. If force_all is set (operator requested FORCE_REBUILD for this package), force
       all stages, ignoring cache/force_run entirely.
    2. If any dependency was rebuilt this run, force all stages
    3. If any stage has force_run=true, that stage and all downstream stages are forced

    Args:
        pkg: Package name
        deps: Package's effective dependencies (see lib.deps.effective_deps)
        target: build_db target key (mock chroot, e.g. fedora-44-x86_64)
        rebuilt_packages: Set of packages that were rebuilt this run
        force_all: If True, force every stage for this package (FORCE_REBUILD=1)

    Returns:
        Set of stage names that must run
    """
    if force_all:
        return set(STAGE_ORDER)

    forced: set[str] = set()
    cascade = False

    # If any dependency was rebuilt this run, force all stages
    if any(dep in rebuilt_packages for dep in deps):
        return set(STAGE_ORDER)

    # Check each stage for force_run flag; once found, cascade to remaining stages
    for stage in STAGE_ORDER:
        entry = build_db.get_stage(pkg, stage, target) or {}
        if cascade or entry.get("force_run", False):
            forced.add(stage)
            cascade = True
    return forced


def is_cached(
    stage: str, pkg: str, target: str, new_hashes: dict, forced_stages: set[str]
) -> bool:
    """Check if a stage result is cached and can be skipped.

    A stage is cached if:
    - Its state is "success"
    - Its stored hashes match current input hashes
    - It's not in the forced_stages set

    Args:
        stage: Stage name
        pkg: Package name
        target: build_db target key
        new_hashes: Newly computed input hashes for this stage
        forced_stages: Set of stages that must run (cannot be skipped)

    Returns:
        True if stage can be skipped (is cached), False if it must run
    """
    if stage in forced_stages:
        return False
    entry = build_db.get_stage(pkg, stage, target)
    if entry is None:
        return False
    if not (entry.get("state") == "success" and hashes_match(entry, new_hashes)):
        return False
    return artifacts_present(stage, pkg, target, entry.get("version"))


def cache_miss_reason(
    stage: str,
    pkg: str,
    target: str,
    new_hashes: dict,
    forced_stages: set[str],
    deps: set[str] | None = None,
    rebuilt_packages: set[str] | None = None,
) -> str:
    """Determine why a stage cache was missed (not cached).

    Returns a reason string explaining why is_cached() returned False.
    Used as the `reason` recorded on stage rows that run.

    Args:
        stage: Stage name
        pkg: Package name
        target: build_db target key
        new_hashes: Newly computed input hashes
        forced_stages: Set of stages forced to run
        deps: Package's effective dependencies (see lib.deps.effective_deps),
            used to detect dependency-based force
        rebuilt_packages: Set of packages rebuilt this run (to show in reason)

    Returns:
        Canonical reason string. Full vocabulary (some set here, some set
        directly by full-cycle.py/stage scripts for cases that aren't cache
        misses):
        - "cached" — cache hit, hashes match (full-cycle.py, via update_reason)
        - "forced" — force_run flag set by operator
        - "forced (dep rebuilt: hyprutils)" — dependency was rebuilt
        - "forced (dep rebuilt: hyprutils, hyprlang)" — multiple deps rebuilt
        - "hash-mismatch" — stored hashes differ from computed
        - "artifact-missing" — hashes match, but the artifact recorded for this
          NVR is no longer on disk (see artifacts_present())
        - "prior-failed" — prior state was "failed"
        - "prior-skipped" — prior state was "skipped"
        - "first-run" — no prior entry exists
        - "proceed-skip" — PROCEED_BUILD=true, prior state success (full-cycle.py)
        - "SKIP_MOCK" / "SKIP_COPR" — env var skip (full-cycle.py)
        - "config: skip" — fedora:<ver>: skip: true in packages.yaml (stage scripts)
        - "not-vendored" — vendor skipped, package is not Go/Rust (stage-vendor.py)
        - "vendor-store hit" — vendor tarball copied from the content-addressed
          store (lib/vendor_store.py) instead of rebuilt (stage-vendor.py)
        - "spec failed" — spec stage failed (vendor/srpm downstream) (stage scripts)
        - "source verify failed" — downloaded source file has no entry in, or
          doesn't match, sources.lock.yaml (stage-srpm.py, see docs/bugs.md BUG-0025)
        - "srpm {state}" — srpm upstream (mock/copr) (stage scripts)
        - "srpm artifact missing" — srpm row is success but its recorded file is
          gone from disk (stage-mock.py/stage-copr.py, see docs/bugs.md BUG-0015)
        - "mock {state}" — mock upstream (copr) (stage scripts)
        - "local dep failed: <name>" — local dep failed in mock (stage-mock.py)

    Note: When listing rebuilt dependencies, only includes deps that actually changed
    (reason != "cached"). Cached dependencies are filtered out even if in rebuilt_packages.
    """
    if stage in forced_stages:
        # Check if forced due to dependency rebuild
        if deps and rebuilt_packages:
            # Filter to only include deps that actually changed (not cached).
            # Sorted for deterministic output (deps is a set).
            rebuilt_deps = [
                dep
                for dep in sorted(deps)
                if dep in rebuilt_packages
                and (build_db.get_stage(dep, stage, target) or {}).get("reason")
                != "cached"
            ]
            if rebuilt_deps:
                deps_str = ", ".join(rebuilt_deps)
                return f"forced (dep rebuilt: {deps_str})"
        return "forced"

    entry = build_db.get_stage(pkg, stage, target)
    if entry is None:
        return "first-run"

    state = entry.get("state")
    if state != "success":
        return f"prior-{state}"

    if hashes_match(entry, new_hashes) and not artifacts_present(
        stage, pkg, target, entry.get("version")
    ):
        return "artifact-missing"

    return "hash-mismatch"
