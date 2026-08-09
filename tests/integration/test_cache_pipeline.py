"""Integration tests for cache invalidation (is_cached / compute_forced_stages)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib import build_db, paths
from lib.cache import hashes_match
from lib.pipeline import is_cached, compute_forced_stages, STAGE_ORDER

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed(pkg: str, stage: str, hashes: dict | None = None, **fields) -> None:
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    state = fields.pop("state", "success")
    build_db.set_stage(pkg, stage, TARGET, run_id, state, **fields)
    if hashes is not None:
        build_db.finalize_stage(pkg, stage, TARGET, started_at=1, hashes=hashes)


# Maps a stage to the artifacts.kind it's expected to have on disk once
# successful -- mirrors lib.pipeline._STAGE_ARTIFACT_KINDS. is_cached() now
# checks this (docs/bugs.md BUG-0015), so tests asserting a "success" stage
# is cached must seed a real, existing artifact for it, not just a DB row.
_ARTIFACT_KIND_BY_STAGE = {"vendor": "vendor", "srpm": "srpm", "mock": "rpm"}


def _seed_matching_artifact(tmp_path, pkg: str, stage: str, version: str | None) -> None:
    """Write a real file and record it as this stage's artifact, if tracked."""
    kind = _ARTIFACT_KIND_BY_STAGE.get(stage)
    if kind is None:
        return
    artifact = tmp_path / f"{pkg}-{stage}-artifact"
    artifact.write_text("fake artifact")
    build_db.record_artifact(str(artifact), "repo", kind, pkg, TARGET, version)


class TestCachePipeline:
    """Test cache validation and forced stage computation."""

    def test_second_run_detects_cache_hit(self):
        """is_cached returns True when hashes match and state is success."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        _seed("pkg-a", "spec", hashes=hashes, version="1.0-1.fc43")

        # Same hashes should be cached
        result = is_cached("spec", "pkg-a", TARGET, hashes, set())
        assert result is True

    def test_changed_template_invalidates_cache(self):
        """is_cached returns False when templates hash differs."""
        old_hashes = {"source_commit": "abc123", "templates": "old_template"}
        new_hashes = {"source_commit": "abc123", "templates": "new_template"}
        _seed("pkg-a", "spec", hashes=old_hashes, version="1.0-1.fc43")

        result = is_cached("spec", "pkg-a", TARGET, new_hashes, set())
        assert result is False

    def test_force_run_flag_invalidates_cache_even_with_matching_hashes(self):
        """is_cached returns False when stage is in forced_stages."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        _seed("pkg-a", "spec", hashes=hashes, version="1.0-1.fc43", force_run=1)

        # Even with matching hashes, forced stages are not cached
        forced_stages = {"spec", "vendor", "srpm", "mock", "copr"}
        result = is_cached("spec", "pkg-a", TARGET, hashes, forced_stages)
        assert result is False

    def test_rebuilt_dependency_forces_all_stages(self):
        """compute_forced_stages returns all stages when dependency rebuilt."""
        deps = {"pkg-b"}
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage)
        rebuilt = {"pkg-b"}

        forced = compute_forced_stages("pkg-a", deps, TARGET, rebuilt)
        assert forced == set(STAGE_ORDER)

    def test_downstream_cascade_from_srpm_force_run(self):
        """Force run at srpm cascades to mock and copr."""
        deps = set()
        _seed("pkg-a", "spec", force_run=0)
        _seed("pkg-a", "vendor", force_run=0)
        _seed("pkg-a", "srpm", force_run=1)
        _seed("pkg-a", "mock", force_run=0)
        _seed("pkg-a", "copr", force_run=0)

        forced = compute_forced_stages("pkg-a", deps, TARGET, set())
        assert forced == {"srpm", "mock", "copr"}

    def test_no_force_and_matching_hashes_all_cached(self, tmp_path):
        """is_cached returns True for all stages with no force_run and matching hashes."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage, hashes=hashes, version="1.0-1.fc43")
            _seed_matching_artifact(tmp_path, "pkg-a", stage, "1.0-1.fc43")

        deps = set()
        forced = compute_forced_stages("pkg-a", deps, TARGET, set())
        assert forced == set()

        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-a", TARGET, hashes, forced)
            assert result is True

    def test_missing_entry_not_cached(self):
        """is_cached returns False when entry missing."""
        hashes = {"source_commit": "abc123"}
        result = is_cached("spec", "pkg-a", TARGET, hashes, set())
        assert result is False

    def test_failed_state_not_cached(self):
        """is_cached returns False when state is failed."""
        _seed("pkg-a", "spec", hashes={"source_commit": "abc123"}, state="failed")

        result = is_cached("spec", "pkg-a", TARGET, {"source_commit": "abc123"}, set())
        assert result is False

    def test_early_stage_force_cascades_downstream(self):
        """Force run at spec cascades to vendor, srpm, mock, copr."""
        deps = set()
        _seed("pkg-a", "spec", force_run=1)
        _seed("pkg-a", "vendor", force_run=0)
        _seed("pkg-a", "srpm", force_run=0)
        _seed("pkg-a", "mock", force_run=0)
        _seed("pkg-a", "copr", force_run=0)

        forced = compute_forced_stages("pkg-a", deps, TARGET, set())
        assert forced == set(STAGE_ORDER)

    def test_no_dependencies_returns_empty_forced_set(self):
        """compute_forced_stages returns empty set when no force_run and no rebuilt deps."""
        deps = set()
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage, force_run=0)

        forced = compute_forced_stages("pkg-a", deps, TARGET, set())
        assert forced == set()

    def test_force_all_forces_every_stage_even_with_fresh_matching_hashes(self, tmp_path):
        """force_all=True (FORCE_REBUILD) forces every stage regardless of cache state."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage, hashes=hashes, version="1.0-1.fc43", force_run=0)
            _seed_matching_artifact(tmp_path, "pkg-a", stage, "1.0-1.fc43")

        forced = compute_forced_stages("pkg-a", set(), TARGET, set(), force_all=True)
        assert forced == set(STAGE_ORDER)

        for stage in STAGE_ORDER:
            assert is_cached(stage, "pkg-a", TARGET, hashes, forced) is False

    def test_force_all_false_is_unaffected(self):
        """force_all defaults to False and doesn't change existing no-force behaviour."""
        deps = set()
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage, force_run=0)

        forced = compute_forced_stages("pkg-a", deps, TARGET, set(), force_all=False)
        assert forced == set()


class TestShowPlanMatchesExecution:
    """Test that show_plan output matches what execution will do."""

    def test_plan_shows_run_when_execution_will_run_due_to_hash_diff(self):
        """Plan reflects hash diff: shows 'run' when hashes changed."""
        # Old build succeeded with old hashes
        old_hashes = {"source_commit": "old_commit_hash"}
        for stage in ("spec", "vendor", "srpm", "mock", "copr"):
            _seed("pkg-a", stage, hashes=old_hashes)

        # New hashes differ (submodule commit changed)
        new_hashes = {"source_commit": "new_commit_hash"}

        # With old hashes stored, is_cached would return False (hash mismatch)
        result = is_cached("spec", "pkg-a", TARGET, new_hashes, set())
        assert result is False, "Stage should not be cached when hashes differ"

    def test_plan_reflects_dep_cascade_forces_downstream(self):
        """Plan shows 'run' for all stages when dependency is rebuilt."""
        # Setup: pkg-b depends on pkg-a
        deps_b = {"pkg-a"}

        # pkg-a was rebuilt in this run
        rebuilt = {"pkg-a"}

        # Query: what stages of pkg-b must run?
        for stage in STAGE_ORDER:
            _seed("pkg-b", stage, force_run=0)

        forced_b = compute_forced_stages("pkg-b", deps_b, TARGET, rebuilt)

        # All stages of pkg-b should be forced due to dep rebuild
        assert forced_b == set(STAGE_ORDER)

        # Verify is_cached respects forced_stages
        hashes = {"source_commit": "same"}
        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-b", TARGET, hashes, forced_b)
            assert result is False, f"{stage} should not be cached when forced"

    def test_plan_cache_logic_matches_execution_on_second_run(self, tmp_path):
        """After successful first run, unchanged inputs should be cached."""
        # Simulate second run: nothing changed
        hashes = {"source_commit": "abc123", "templates": "def456"}
        for stage in STAGE_ORDER:
            _seed("pkg-a", stage, hashes=hashes)
            _seed_matching_artifact(tmp_path, "pkg-a", stage, None)

        deps = set()
        forced = compute_forced_stages("pkg-a", deps, TARGET, set())

        # No forced stages, no rebuilt deps
        assert forced == set()

        # All stages should be cached (no hash changes, no forcing)
        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-a", TARGET, hashes, forced)
            assert result is True, f"{stage} should be cached on second run"
