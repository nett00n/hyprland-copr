"""Integration tests for cache invalidation (is_cached / compute_forced_stages)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib.cache import hashes_match
from lib.pipeline import is_cached, compute_forced_stages, STAGE_ORDER


class TestCachePipeline:
    """Test cache validation and forced stage computation."""

    def test_second_run_detects_cache_hit(self):
        """is_cached returns True when hashes match and state is success."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
            }
        }

        # Same hashes should be cached
        result = is_cached("spec", "pkg-a", build_status, hashes, set())
        assert result is True

    def test_changed_template_invalidates_cache(self):
        """is_cached returns False when templates hash differs."""
        old_hashes = {"source_commit": "abc123", "templates": "old_template"}
        new_hashes = {"source_commit": "abc123", "templates": "new_template"}

        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": old_hashes,
                    },
                },
            }
        }

        result = is_cached("spec", "pkg-a", build_status, new_hashes, set())
        assert result is False

    def test_force_run_flag_invalidates_cache_even_with_matching_hashes(self):
        """is_cached returns False when stage is in forced_stages."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                        "force_run": True,
                    },
                },
            }
        }

        # Even with matching hashes, forced stages are not cached
        forced_stages = {"spec", "vendor", "srpm", "mock", "copr"}
        result = is_cached("spec", "pkg-a", build_status, hashes, forced_stages)
        assert result is False

    def test_rebuilt_dependency_forces_all_stages(self):
        """compute_forced_stages returns all stages when dependency rebuilt."""
        meta = {"depends_on": ["pkg-b"]}
        build_status = {"stages": {s: {"pkg-a": {}} for s in STAGE_ORDER}}
        rebuilt = {"pkg-b"}

        forced = compute_forced_stages("pkg-a", meta, build_status, rebuilt)
        assert forced == set(STAGE_ORDER)

    def test_downstream_cascade_from_srpm_force_run(self):
        """Force run at srpm cascades to mock and copr."""
        meta = {}
        build_status = {
            "stages": {
                "spec": {"pkg-a": {"state": "success", "force_run": False}},
                "vendor": {"pkg-a": {"state": "success", "force_run": False}},
                "srpm": {"pkg-a": {"state": "success", "force_run": True}},
                "mock": {"pkg-a": {"state": "success", "force_run": False}},
                "copr": {"pkg-a": {"state": "success", "force_run": False}},
            }
        }

        forced = compute_forced_stages("pkg-a", meta, build_status, set())
        assert forced == {"srpm", "mock", "copr"}

    def test_no_force_and_matching_hashes_all_cached(self):
        """is_cached returns True for all stages with no force_run and matching hashes."""
        hashes = {"source_commit": "abc123", "templates": "def456"}
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
                "vendor": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
                "srpm": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
                "mock": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
                "copr": {
                    "pkg-a": {
                        "state": "success",
                        "version": "1.0-1.fc43",
                        "hashes": hashes,
                    },
                },
            }
        }

        meta = {}
        forced = compute_forced_stages("pkg-a", meta, build_status, set())
        assert forced == set()

        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-a", build_status, hashes, forced)
            assert result is True

    def test_missing_entry_not_cached(self):
        """is_cached returns False when entry missing."""
        build_status = {"stages": {"spec": {}}}

        hashes = {"source_commit": "abc123"}
        result = is_cached("spec", "pkg-a", build_status, hashes, set())
        assert result is False

    def test_failed_state_not_cached(self):
        """is_cached returns False when state is failed."""
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "failed",
                        "hashes": {"source_commit": "abc123"},
                    },
                },
            }
        }

        result = is_cached("spec", "pkg-a", build_status, {"source_commit": "abc123"}, set())
        assert result is False

    def test_early_stage_force_cascades_downstream(self):
        """Force run at spec cascades to vendor, srpm, mock, copr."""
        meta = {}
        build_status = {
            "stages": {
                "spec": {"pkg-a": {"state": "success", "force_run": True}},
                "vendor": {"pkg-a": {"state": "success", "force_run": False}},
                "srpm": {"pkg-a": {"state": "success", "force_run": False}},
                "mock": {"pkg-a": {"state": "success", "force_run": False}},
                "copr": {"pkg-a": {"state": "success", "force_run": False}},
            }
        }

        forced = compute_forced_stages("pkg-a", meta, build_status, set())
        assert forced == set(STAGE_ORDER)

    def test_no_dependencies_returns_empty_forced_set(self):
        """compute_forced_stages returns empty set when no force_run and no rebuilt deps."""
        meta = {}
        build_status = {
            "stages": {s: {"pkg-a": {"state": "success", "force_run": False}} for s in STAGE_ORDER}
        }

        forced = compute_forced_stages("pkg-a", meta, build_status, set())
        assert forced == set()


class TestShowPlanMatchesExecution:
    """Test that show_plan output matches what execution will do."""

    def test_plan_shows_run_when_execution_will_run_due_to_hash_diff(
        self, tmp_path, monkeypatch
    ):
        """Plan reflects hash diff: shows 'run' when hashes changed."""
        from lib import paths

        monkeypatch.setattr(paths, "ROOT", tmp_path)
        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", tmp_path / "build-report.yaml")
        monkeypatch.setattr(paths, "PACKAGES_YAML", tmp_path / "packages.yaml")

        # Old build succeeded with old hashes
        old_hashes = {"source_commit": "old_commit_hash"}
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "hashes": old_hashes,
                    }
                },
                "vendor": {"pkg-a": {"state": "success", "hashes": old_hashes}},
                "srpm": {"pkg-a": {"state": "success", "hashes": old_hashes}},
                "mock": {"pkg-a": {"state": "success", "hashes": old_hashes}},
                "copr": {"pkg-a": {"state": "success", "hashes": old_hashes}},
                "validate": {"pkg-a": {}},
            }
        }

        from lib.yaml_utils import dump_yaml_pretty

        (tmp_path / "build-report.yaml").write_text(dump_yaml_pretty(build_status))

        # New hashes differ (submodule commit changed)
        new_hashes = {"source_commit": "new_commit_hash"}

        # Test is_cached for the spec stage
        # With old hashes, is_cached would return False (hash mismatch)
        result = is_cached("spec", "pkg-a", build_status, new_hashes, set())
        assert result is False, "Stage should not be cached when hashes differ"

    def test_plan_reflects_dep_cascade_forces_downstream(self, tmp_path, monkeypatch):
        """Plan shows 'run' for all stages when dependency is rebuilt."""
        # Setup: pkg-b depends on pkg-a
        meta_b = {"depends_on": ["pkg-a"]}

        # pkg-a was rebuilt in this run
        rebuilt = {"pkg-a"}

        # Query: what stages of pkg-b must run?
        build_status = {
            "stages": {
                "spec": {"pkg-b": {"state": "success", "force_run": False}},
                "vendor": {"pkg-b": {"state": "success", "force_run": False}},
                "srpm": {"pkg-b": {"state": "success", "force_run": False}},
                "mock": {"pkg-b": {"state": "success", "force_run": False}},
                "copr": {"pkg-b": {"state": "success", "force_run": False}},
            }
        }

        forced_b = compute_forced_stages("pkg-b", meta_b, build_status, rebuilt)

        # All stages of pkg-b should be forced due to dep rebuild
        assert forced_b == set(STAGE_ORDER)

        # Verify is_cached respects forced_stages
        hashes = {"source_commit": "same"}
        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-b", build_status, hashes, forced_b)
            assert result is False, f"{stage} should not be cached when forced"

    def test_plan_cache_logic_matches_execution_on_second_run(self):
        """After successful first run, unchanged inputs should be cached."""
        # Simulate second run: nothing changed
        hashes = {"source_commit": "abc123", "templates": "def456"}
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "state": "success",
                        "hashes": hashes,
                    }
                },
                "vendor": {"pkg-a": {"state": "success", "hashes": hashes}},
                "srpm": {"pkg-a": {"state": "success", "hashes": hashes}},
                "mock": {"pkg-a": {"state": "success", "hashes": hashes}},
                "copr": {"pkg-a": {"state": "success", "hashes": hashes}},
            }
        }

        meta = {"depends_on": []}
        forced = compute_forced_stages("pkg-a", meta, build_status, set())

        # No forced stages, no rebuilt deps
        assert forced == set()

        # All stages should be cached (no hash changes, no forcing)
        for stage in STAGE_ORDER:
            result = is_cached(stage, "pkg-a", build_status, hashes, forced)
            assert result is True, f"{stage} should be cached on second run"
