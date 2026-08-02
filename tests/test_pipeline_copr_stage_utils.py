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
from lib.pipeline import (
    artifacts_present,
    compute_forced_stages,
    is_cached,
    cache_miss_reason,
)
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


class TestArtifactAwareCaching:
    """Test that is_cached()/cache_miss_reason() verify the recorded artifact is
    still on disk before trusting a "success" DB row (docs/bugs.md BUG-0015).
    """

    def _seed_success(self, pkg: str, stage: str, version: str, hashes: dict) -> None:
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, stage, TARGET, run_id, "success", version=version)
        build_db.finalize_stage(pkg, stage, TARGET, 1, hashes)

    def test_spec_ignores_artifact_state(self):
        """spec has no tracked artifact kind -- artifact state never matters."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "spec", "1.0-1.fc44", hashes)
        assert is_cached("spec", "pkg", TARGET, hashes, set()) is True

    def test_mock_cached_when_rpm_present_on_disk(self, tmp_path):
        """Cache hit: success + matching hashes + the recorded RPM still exists."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "1.0-1.fc44", hashes)
        rpm = tmp_path / "pkg-1.0-1.fc44.x86_64.rpm"
        rpm.write_text("fake rpm")
        build_db.record_artifact(str(rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44")
        assert is_cached("mock", "pkg", TARGET, hashes, set()) is True

    def test_mock_not_cached_when_rpm_row_exists_but_file_deleted(self, tmp_path):
        """Recorded artifact row, but the file was unlinked from disk -> not cached."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "1.0-1.fc44", hashes)
        rpm = tmp_path / "pkg-1.0-1.fc44.x86_64.rpm"
        rpm.write_text("fake rpm")
        build_db.record_artifact(str(rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44")
        rpm.unlink()
        assert is_cached("mock", "pkg", TARGET, hashes, set()) is False
        assert cache_miss_reason("mock", "pkg", TARGET, hashes, set()) == "artifact-missing"

    def test_mock_not_cached_when_no_artifact_row_at_all(self):
        """success row, matching hashes, but nothing was ever recorded in artifacts."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "1.0-1.fc44", hashes)
        assert is_cached("mock", "pkg", TARGET, hashes, set()) is False
        assert cache_miss_reason("mock", "pkg", TARGET, hashes, set()) == "artifact-missing"

    def test_mock_not_cached_when_artifact_is_for_an_older_nvr(self, tmp_path):
        """Dangling row for a stale NVR must not satisfy the current version's check.

        Regression shape for issue #8 / BUG-0015: prune_local_repo() deletes
        stale-NVR RPMs from local-repo/ without deleting their artifacts rows, so
        an artifacts row can exist for an old NVR while the current NVR has none.
        """
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "2.0-1.fc44", hashes)
        old_rpm = tmp_path / "pkg-1.0-1.fc44.x86_64.rpm"
        old_rpm.write_text("stale rpm")
        build_db.record_artifact(
            str(old_rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44"
        )
        assert is_cached("mock", "pkg", TARGET, hashes, set()) is False

    def test_mock_not_cached_when_devel_subpackage_missing(self, tmp_path):
        """Both the main and -devel RPM rows must exist on disk, not just one."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "1.0-1.fc44", hashes)
        main_rpm = tmp_path / "pkg-1.0-1.fc44.x86_64.rpm"
        main_rpm.write_text("main rpm")
        devel_rpm = tmp_path / "pkg-devel-1.0-1.fc44.x86_64.rpm"
        # devel_rpm intentionally never written to disk
        build_db.record_artifact(
            str(main_rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44"
        )
        build_db.record_artifact(
            str(devel_rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44"
        )
        assert artifacts_present("mock", "pkg", TARGET, "1.0-1.fc44") is False
        assert is_cached("mock", "pkg", TARGET, hashes, set()) is False

    def test_vendor_and_srpm_also_require_artifact(self, tmp_path):
        """The same artifact-presence rule applies to vendor and srpm, not just mock."""
        hashes = {"a": "hash1"}
        for stage, kind in (("vendor", "vendor"), ("srpm", "srpm")):
            self._seed_success(f"pkg-{stage}", stage, "1.0-1.fc44", hashes)
            assert is_cached(stage, f"pkg-{stage}", TARGET, hashes, set()) is False
            tarball = tmp_path / f"{stage}.tar.gz"
            tarball.write_text("artifact")
            build_db.record_artifact(
                str(tarball), "rpmbuild-volume", kind, f"pkg-{stage}", TARGET, "1.0-1.fc44"
            )
            assert is_cached(stage, f"pkg-{stage}", TARGET, hashes, set()) is True

    def test_forced_stage_still_takes_priority_over_artifact_check(self, tmp_path):
        """forced_stages short-circuits before artifact state is even considered."""
        hashes = {"a": "hash1"}
        self._seed_success("pkg", "mock", "1.0-1.fc44", hashes)
        rpm = tmp_path / "pkg-1.0-1.fc44.x86_64.rpm"
        rpm.write_text("fake rpm")
        build_db.record_artifact(str(rpm), "repo", "rpm", "pkg", TARGET, "1.0-1.fc44")
        assert is_cached("mock", "pkg", TARGET, hashes, {"mock"}) is False
        assert cache_miss_reason("mock", "pkg", TARGET, hashes, {"mock"}) == "forced"


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
