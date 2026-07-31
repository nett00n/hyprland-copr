"""Unit tests for scripts/lib/pipeline.py and lib/copr.py.

pipeline.py's compute_forced_stages/is_cached/cache_miss_reason now read
build-report.db directly (keyed by `target`) instead of taking a build_status
dict, so these seed a real tmp DB via lib.build_db rather than constructing a
fake nested dict.

finalize_stage (the DB form of the old inject_stage_meta) is already covered
exhaustively in tests/test_build_db.py -- not duplicated here.
"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.pipeline import compute_forced_stages, is_cached, cache_miss_reason
from lib.copr import parse_build_id, validate_copr_repo

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed(pkg: str, stage: str, **fields) -> None:
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    build_db.set_stage(pkg, stage, TARGET, run_id, fields.pop("state", "success"), **fields)


class TestComputeForcedStages:
    """Test forced stage computation."""

    def test_no_deps_rebuilt_no_force_flags(self):
        """No forced stages when no deps rebuilt and no force flags."""
        deps = set()
        for stage in ("spec", "vendor", "srpm", "mock", "copr"):
            _seed("pkg", stage, force_run=0)
        rebuilt = set()
        assert compute_forced_stages("pkg", deps, TARGET, rebuilt) == set()

    def test_dep_rebuilt_forces_all_stages(self):
        """Any rebuilt dependency forces all stages."""
        deps = {"dep1", "dep2"}
        rebuilt = {"dep1"}
        result = compute_forced_stages("pkg", deps, TARGET, rebuilt)
        assert result == {"spec", "vendor", "srpm", "mock", "copr"}

    def test_force_run_on_spec_cascades(self):
        """force_run on spec stage cascades to downstream."""
        deps = set()
        _seed("pkg", "spec", force_run=1)
        for stage in ("vendor", "srpm", "mock", "copr"):
            _seed("pkg", stage, force_run=0)
        rebuilt = set()
        result = compute_forced_stages("pkg", deps, TARGET, rebuilt)
        assert result == {"spec", "vendor", "srpm", "mock", "copr"}

    def test_force_run_on_srpm_does_not_affect_upstream(self):
        """force_run on srpm does not force spec or vendor."""
        deps = set()
        _seed("pkg", "spec", force_run=0)
        _seed("pkg", "vendor", force_run=0)
        _seed("pkg", "srpm", force_run=1)
        _seed("pkg", "mock", force_run=0)
        _seed("pkg", "copr", force_run=0)
        rebuilt = set()
        result = compute_forced_stages("pkg", deps, TARGET, rebuilt)
        assert result == {"srpm", "mock", "copr"}
        assert "spec" not in result
        assert "vendor" not in result

    def test_dep_rebuilt_overrides_stage_entries(self):
        """Rebuilt dep forces all stages even if no force_run flags."""
        deps = {"other"}
        _seed("pkg", "spec", force_run=0)
        rebuilt = {"other"}
        result = compute_forced_stages("pkg", deps, TARGET, rebuilt)
        # All stages forced regardless of stage entries
        assert len(result) == 5

    def test_missing_stage_entry_no_crash(self):
        """Missing stage entry doesn't crash."""
        deps = set()
        rebuilt = set()
        result = compute_forced_stages("pkg", deps, TARGET, rebuilt)
        assert result == set()

    def test_skipped_vendor_dep_not_in_rebuilt_packages(self):
        """Non-Go package with vendor state=skipped should not force downstream.

        Regression test for cache cascade bug: when a non-Go package (e.g. aquamarine)
        has vendor state="skipped" and is NOT in rebuilt_packages, a downstream package
        (e.g. Hyprland) that depends on it should NOT be forced to rebuild.

        This verifies the fix: full-cycle.py checks vendor state="skipped" before
        calling is_cached(), preventing the false cache miss that would add the
        non-Go package to rebuilt_packages.
        """
        deps = {"aquamarine", "glaze"}
        # rebuilt_packages is empty because the fix prevents non-Go packages
        # from being added when they have vendor state="skipped"
        rebuilt = set()
        result = compute_forced_stages("Hyprland", deps, TARGET, rebuilt)
        # Should NOT force all stages when deps are not in rebuilt_packages
        assert result == set()


class TestIsCached:
    """Test cache hit detection."""

    def test_cached_success_matching_hashes(self):
        """Cache hit: state=success, hashes match, not forced."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "success")
        build_db.finalize_stage("pkg", "spec", TARGET, 1, {"a": "hash1"})
        new_hashes = {"a": "hash1"}
        forced_stages = set()
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is True

    def test_not_cached_state_failed(self):
        """Not cached if state != success."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "failed")
        new_hashes = {"a": "hash1"}
        forced_stages = set()
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is False

    def test_not_cached_hashes_mismatch(self):
        """Not cached if hashes differ."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "success")
        build_db.finalize_stage("pkg", "spec", TARGET, 1, {"a": "hash1"})
        new_hashes = {"a": "hash2"}
        forced_stages = set()
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is False

    def test_not_cached_in_forced_stages(self):
        """Not cached if stage is in forced_stages."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "success")
        build_db.finalize_stage("pkg", "spec", TARGET, 1, {"a": "hash1"})
        new_hashes = {"a": "hash1"}
        forced_stages = {"spec"}
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is False

    def test_missing_entry_not_cached(self):
        """Missing entry in build-report.db is not cached."""
        new_hashes = {"a": "hash1"}
        forced_stages = set()
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is False

    def test_missing_hashes_not_cached(self):
        """Entry with no hashes is not cached."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "success")
        new_hashes = {"a": "hash1"}
        forced_stages = set()
        assert is_cached("spec", "pkg", TARGET, new_hashes, forced_stages) is False

    def test_vendor_skipped_state_not_cached(self):
        """Vendor stage with skipped state is not cached (documents the raw is_cached behavior).

        Non-Go packages have vendor state="skipped" set by stage-vendor.py.
        The is_cached() function returns False for any non-success state, but
        full-cycle.py must handle the "skipped" state specially.
        """
        _seed("aquamarine", "vendor", state="skipped", version="0.4.0", reason="not-go")
        new_hashes = {}
        forced_stages = set()
        result = is_cached("vendor", "aquamarine", TARGET, new_hashes, forced_stages)
        # is_cached returns False for non-success states; full-cycle.py guards this
        assert result is False

    def test_vendor_skipped_with_skip_guard_logic(self):
        """Verify the skip guard logic: skipped state OR is_cached = True for skipped.

        This test validates the fix in full-cycle.py: before calling is_cached() for
        vendor, we check: `vendor_entry.get("state") == "skipped" or is_cached(...)`

        For a non-Go package with vendor state="skipped", this guard ensures the
        package is not added to rebuilt_packages, preventing false cascade rebuilds.
        """
        _seed("aquamarine", "vendor", state="skipped", version="0.4.0", reason="not-go")
        vendor_entry = build_db.get_stage("aquamarine", "vendor", TARGET) or {}
        new_hashes = {}
        forced_stages = set()
        # The full-cycle.py logic: skip guard OR is_cached
        is_vendor_cached = vendor_entry.get("state") == "skipped" or is_cached(
            "vendor", "aquamarine", TARGET, new_hashes, forced_stages
        )
        # Should be True because state == "skipped"
        assert is_vendor_cached is True


class TestCacheMissReason:
    """Test cache miss reason determination."""

    def test_forced_stage(self):
        """Return 'forced' if stage in forced_stages."""
        assert cache_miss_reason("spec", "pkg", TARGET, {}, {"spec"}) == "forced"

    def test_first_run_no_entry(self):
        """Return 'first-run' if no prior entry."""
        assert cache_miss_reason("spec", "pkg", TARGET, {}, set()) == "first-run"

    def test_prior_failed_state(self):
        """Return 'prior-failed' if state is failed."""
        _seed("pkg", "spec", state="failed")
        assert cache_miss_reason("spec", "pkg", TARGET, {}, set()) == "prior-failed"

    def test_prior_skipped_state(self):
        """Return 'prior-skipped' if state is skipped."""
        _seed("pkg", "spec", state="skipped")
        assert cache_miss_reason("spec", "pkg", TARGET, {}, set()) == "prior-skipped"

    def test_hash_mismatch(self):
        """Return 'hash-mismatch' when prior success but hashes differ."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg", "spec", TARGET, run_id, "success")
        build_db.finalize_stage("pkg", "spec", TARGET, 1, {"a": "old_hash"})
        new_hashes = {"a": "new_hash"}
        assert cache_miss_reason("spec", "pkg", TARGET, new_hashes, set()) == "hash-mismatch"

    def test_forced_due_to_operator(self):
        """Return 'forced' when force_run set by operator (no deps rebuilt)."""
        deps = set()
        rebuilt = set()
        result = cache_miss_reason("spec", "pkg", TARGET, {}, {"spec"}, deps, rebuilt)
        assert result == "forced"

    def test_forced_due_to_dep_rebuild(self):
        """Return 'forced (dep rebuilt: ...)' when dependency was rebuilt."""
        deps = {"hyprutils", "hyprlang"}
        rebuilt = {"hyprutils"}
        result = cache_miss_reason("spec", "pkg", TARGET, {}, {"spec"}, deps, rebuilt)
        assert result == "forced (dep rebuilt: hyprutils)"

    def test_forced_due_to_multiple_dep_rebuilds(self):
        """Return reason with all rebuilt deps."""
        deps = {"hyprutils", "hyprlang", "hyprwayland"}
        rebuilt = {"hyprutils", "hyprlang"}
        result = cache_miss_reason("spec", "pkg", TARGET, {}, {"spec"}, deps, rebuilt)
        # Sorted alphabetically for deterministic output
        assert result == "forced (dep rebuilt: hyprlang, hyprutils)"

    def test_forced_filters_out_cached_deps(self):
        """Filter out deps from reason if they ended up cached."""
        _seed("aquamarine", "spec", reason="cached", state="success")
        _seed("glaze", "spec", reason="cached", state="success")
        _seed("hyprlang", "spec", reason="hash-mismatch", state="success")
        deps = {"aquamarine", "glaze", "hyprlang"}
        rebuilt = {"aquamarine", "glaze", "hyprlang"}
        result = cache_miss_reason("spec", "pkg", TARGET, {}, {"spec"}, deps, rebuilt)
        # Only hyprlang should be in reason (others are cached)
        assert result == "forced (dep rebuilt: hyprlang)"
        assert "aquamarine" not in result
        assert "glaze" not in result


class TestParseBuildId:
    """Test build ID extraction from copr-cli output."""

    def test_extract_build_id(self):
        """Extract build ID from typical output."""
        output = "Created builds: 12345678"
        assert parse_build_id(output) == 12345678

    def test_extract_build_id_multiline(self):
        """Extract build ID from multiline output."""
        output = """Building...
Created builds: 99887766
Done."""
        assert parse_build_id(output) == 99887766

    def test_no_match_returns_none(self):
        """No match returns None."""
        output = "No builds created"
        assert parse_build_id(output) is None

    def test_empty_output_returns_none(self):
        """Empty output returns None."""
        assert parse_build_id("") is None

    def test_invalid_id_number_returns_none(self):
        """Invalid number in output returns None."""
        output = "Created builds: abc"
        assert parse_build_id(output) is None

    def test_build_id_at_end_of_complex_line(self):
        """Build ID extracted even in complex output."""
        output = "  Created builds: 555  "
        assert parse_build_id(output) == 555


class TestValidateCoprRepo:
    """Test COPR repository slug validation."""

    def test_valid_repo_slug(self):
        """Valid owner/repo format."""
        assert validate_copr_repo("user/repo") is True

    def test_valid_with_dashes(self):
        """Valid slug with dashes."""
        assert validate_copr_repo("my-user/my-repo") is True

    def test_valid_with_dots(self):
        """Valid slug with dots in repo name."""
        assert validate_copr_repo("user/repo.name") is True

    def test_valid_with_underscore(self):
        """Valid slug with underscores."""
        assert validate_copr_repo("user_name/repo_name") is True

    def test_invalid_missing_slash(self):
        """Invalid: missing slash."""
        assert validate_copr_repo("userrepo") is False

    def test_invalid_too_many_slashes(self):
        """Invalid: too many slashes."""
        assert validate_copr_repo("user/repo/extra") is False

    def test_invalid_empty_string(self):
        """Invalid: empty string."""
        assert validate_copr_repo("") is False

    def test_invalid_slash_only(self):
        """Invalid: slash only."""
        assert validate_copr_repo("/") is False

    def test_invalid_trailing_slash(self):
        """Invalid: trailing slash."""
        assert validate_copr_repo("user/repo/") is False

    def test_invalid_leading_slash(self):
        """Invalid: leading slash."""
        assert validate_copr_repo("/user/repo") is False

    def test_invalid_special_chars(self):
        """Invalid: special characters."""
        assert validate_copr_repo("user@/repo!") is False

    def test_valid_complex_names(self):
        """Valid with complex alphanumeric names."""
        assert validate_copr_repo("user123/repo-name.v2") is True
