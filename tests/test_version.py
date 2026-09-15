"""Unit tests for scripts/lib/version.py"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.version import (
    RELEASE_TYPES,
    latest_semver,
    latest_tag,
    nvr,
    clean_version,
    recorded_version,
    versions_for,
    rpm_version_from_tag,
    rpmvercmp,
    compare_evr,
)


class TestLatestSemver:
    """Test semver tag selection."""

    def test_single_semver_tag(self):
        """Single semver tag is returned."""
        tags = ["v1.0.0"]
        assert latest_semver(tags) == "v1.0.0"

    def test_multiple_semver_tags_highest_wins(self):
        """Highest semver wins."""
        tags = ["v1.0.0", "v2.0.0", "v1.5.0"]
        assert latest_semver(tags) == "v2.0.0"

    def test_semver_without_v_prefix(self):
        """Semver without v prefix is matched."""
        tags = ["1.0.0", "2.0.0"]
        assert latest_semver(tags) == "2.0.0"

    def test_semver_mixed_with_and_without_v(self):
        """Both v and non-v prefixes handled."""
        tags = ["v1.5.0", "2.0.0", "v1.9.0"]
        assert latest_semver(tags) == "2.0.0"

    def test_prerelease_excluded(self):
        """Prerelease suffixes like -beta, -rc are excluded."""
        tags = ["v1.0.0-beta", "v1.0.0-rc1", "v1.0.0"]
        assert latest_semver(tags) == "v1.0.0"

    def test_non_semver_tags_ignored(self):
        """Non-semver tags are skipped."""
        tags = ["latest", "stable", "master", "v1.0"]
        assert latest_semver(tags) is None

    def test_empty_tag_list(self):
        """Empty list returns None."""
        tags = []
        assert latest_semver(tags) is None

    def test_all_non_semver_tags(self):
        """All non-semver tags returns None."""
        tags = ["develop", "release-1", "v1"]
        assert latest_semver(tags) is None

    def test_major_minor_patch_comparison(self):
        """Comparison prioritizes major, then minor, then patch."""
        tags = ["v1.9.9", "v2.0.0", "v1.10.0"]
        assert latest_semver(tags) == "v2.0.0"

    def test_zero_versions(self):
        """Zero versions are handled."""
        tags = ["v0.0.1", "v0.1.0", "v1.0.0"]
        assert latest_semver(tags) == "v1.0.0"

    def test_large_version_numbers(self):
        """Large version numbers work."""
        tags = ["v10.20.30", "v10.20.31", "v10.21.0"]
        assert latest_semver(tags) == "v10.21.0"


class TestLatestTag:
    """Test loose version-like tag selection (BUG-0014's latest-tag)."""

    def test_mpvpaper_real_tags(self):
        """Real upstream tag list: two-component tags beat the lone semver one.

        latest_semver on this same list returns 1.2.1 (the only strict
        three-component tag) -- latest_tag must not make that mistake.
        """
        tags = ["1.0", "1.1", "1.2", "1.2.1", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9"]
        assert latest_tag(tags) == "1.9"

    def test_two_component_ordering(self):
        """1.2 < 1.2.1 < 1.3 by tuple comparison, not string comparison."""
        assert latest_tag(["1.2", "1.2.1", "1.3"]) == "1.3"
        assert latest_tag(["1.2", "1.2.1"]) == "1.2.1"

    def test_v_prefix_stripped_for_comparison_but_kept_verbatim(self):
        """v-prefixed and bare tags compare together; the winner is returned as-is."""
        assert latest_tag(["v1.5.0", "2.0.0", "v1.9.0"]) == "2.0.0"
        assert latest_tag(["v1.0", "v2.0"]) == "v2.0"

    def test_prerelease_ranks_below_same_numbered_release(self):
        assert latest_tag(["2.0.0-rc1", "2.0.0"]) == "2.0.0"

    def test_prerelease_ranks_above_older_release(self):
        assert latest_tag(["1.9", "2.0.0-rc1"]) == "2.0.0-rc1"

    def test_prerelease_ordering_alpha_beta_rc(self):
        tags = ["1.0.0-alpha", "1.0.0-rc", "1.0.0-beta"]
        assert latest_tag(tags) == "1.0.0-rc"

    def test_prerelease_numeric_suffix_ordering(self):
        assert latest_tag(["1.0.0-rc1", "1.0.0-rc2"]) == "1.0.0-rc2"

    def test_junk_tags_skipped(self):
        assert latest_tag(["nightly", "latest", "master"]) is None

    def test_junk_tags_ignored_alongside_real_ones(self):
        assert latest_tag(["nightly", "1.9", "latest"]) == "1.9"

    def test_empty_list(self):
        assert latest_tag([]) is None

    def test_single_component_tag(self):
        assert latest_tag(["5", "3", "10"]) == "10"


class TestRpmVersionFromTag:
    """Test tag -> RPM-legal Version conversion."""

    def test_plain_tag_is_noop(self):
        assert rpm_version_from_tag("1.9") == "1.9"

    def test_v_prefix_stripped(self):
        assert rpm_version_from_tag("v1.9.0") == "1.9.0"

    def test_prerelease_hyphen_becomes_tilde(self):
        assert rpm_version_from_tag("2.0.0-rc1") == "2.0.0~rc1"

    def test_v_prefix_and_prerelease(self):
        assert rpm_version_from_tag("v2.0.0-rc1") == "2.0.0~rc1"


class TestReleaseTypes:
    """RELEASE_TYPES is the single source of truth used by the validators."""

    def test_contains_all_six_types(self):
        assert RELEASE_TYPES == {
            "latest-version",
            "latest-tag",
            "latest-commit",
            "pinned-version",
            "pinned-commit",
            "pinned-tag",
        }


class TestNvr:
    """Test NVR (name-version-release) string formatting."""

    def test_basic_nvr_numeric_version(self):
        """Basic NVR with numeric fedora version."""
        result = nvr("1.0.0", "1", "43")
        assert result == "1.0.0-1.fc43"

    def test_nvr_with_percent_autorelease(self):
        """NVR with %autorelease string."""
        result = nvr("1.2.3", "%autorelease", "44")
        assert result == "1.2.3-%autorelease.fc44"

    def test_nvr_with_manual_rawhide_override(self):
        """rawhide is no longer in SUPPORTED, but FEDORA_VERSION=rawhide still
        works as a manual override (Makefile's MOCK_CHROOT derivation has no
        special case either) -- nvr() formats it like any other version string,
        with no rawhide-specific dist tag."""
        result = nvr("2.0.0", "1", "rawhide")
        assert result == "2.0.0-1.fcrawhide"

    def test_nvr_rawhide_with_complex_version(self):
        """Complex version with a manual rawhide override."""
        result = nvr("0.54.2^20260327git2c4852e", "1", "rawhide")
        assert result == "0.54.2^20260327git2c4852e-1.fcrawhide"

    def test_nvr_string_release(self):
        """Release as a string (not int)."""
        result = nvr("1.0", "5", "43")
        assert result == "1.0-5.fc43"


class TestCleanVersion:
    """Test version cleanup (suffix removal)."""

    def test_already_clean_version(self):
        """Already-clean version is unchanged."""
        assert clean_version("1.0.0") == "1.0.0"

    def test_remove_fc_suffix(self):
        """Removes -1.fc43 suffix."""
        assert clean_version("1.0.0-1.fc43") == "1.0.0"

    def test_remove_autorelease_suffix(self):
        """Removes -%autorelease.fcXX suffix."""
        assert clean_version("1.0.0-%autorelease.fc44") == "1.0.0"

    def test_remove_rawhide_suffix(self):
        """Removes -1.rawhide suffix."""
        assert clean_version("1.0.0-1.rawhide") == "1.0.0"

    def test_with_git_commit_in_version(self):
        """Handles git commit-based versions."""
        assert clean_version("0.54.2^20260327git2c4852e-1.fc43") == "0.54.2^20260327git2c4852e"

    def test_empty_string(self):
        """Empty string returns empty."""
        assert clean_version("") == ""

    def test_version_with_multiple_hyphens(self):
        """Splits only on first hyphen."""
        assert clean_version("1.0-beta-1.fc43") == "1.0"


class TestRecordedVersion:
    """Test recorded_version's precedence and fallback behavior."""

    def test_recorded_wins_over_declared(self):
        """First stage-recorded version wins over the declared packages.yaml one."""
        entries = [{"version": "1.2.0-1.fc43"}, None, None, None]
        meta = {"version": "1.0.0"}
        assert recorded_version(entries, meta) == "1.2.0"

    def test_precedence_spec_srpm_mock_copr(self):
        """Earlier entries in the list win over later ones."""
        entries = [None, {"version": "2.0.0"}, {"version": "3.0.0"}, None]
        assert recorded_version(entries, {}) == "2.0.0"

    def test_none_and_empty_entries_skipped(self):
        """None entries and entries with no/empty version are skipped."""
        entries = [None, {}, {"version": ""}, {"version": "4.0.0"}]
        assert recorded_version(entries, {}) == "4.0.0"

    def test_falls_back_to_declared_version(self):
        """No recorded version anywhere falls back to packages.yaml's declared version."""
        entries = [None, None, None, None]
        meta = {"version": "0.14.0"}
        assert recorded_version(entries, meta) == "0.14.0"

    def test_falls_back_to_dash_when_nothing_available(self):
        """No recorded or declared version yields '-'."""
        assert recorded_version([None, None], {}) == "-"

    def test_recorded_suffix_stripped(self):
        """Recorded version still has its -<release>.fcXX suffix stripped."""
        entries = [{"version": "1.0.0-1.fc43"}]
        assert recorded_version(entries, {}) == "1.0.0"


class TestVersionsFor:
    """Test versions_for's per-package version map."""

    def test_recorded_version_wins(self):
        """A package with a recorded stage version uses that, not the declared one."""
        packages = {"pkg1": {"version": "1.0.0"}}
        stages = {"spec": {"pkg1": {"version": "1.2.0-1.fc43"}}}
        assert versions_for(packages, stages) == {"pkg1": "1.2.0"}

    def test_falls_back_to_declared(self):
        """A package with no recorded stage version falls back to packages.yaml."""
        packages = {"pkg1": {"version": "0.14.0"}}
        assert versions_for(packages, {}) == {"pkg1": "0.14.0"}

    def test_package_absent_from_stages_still_gets_an_entry(self):
        """A package that never appears in `stages` still gets a version entry."""
        packages = {"pkg1": {"version": "1.0.0"}, "pkg2": {"version": "2.0.0"}}
        stages = {"spec": {"pkg1": {"version": "1.0.0-1.fc43"}}}
        assert versions_for(packages, stages) == {"pkg1": "1.0.0", "pkg2": "2.0.0"}


class TestRpmVerCmp:
    """Test rpmvercmp against the canonical rpm vercmp vectors, docs/BUGS.md BUG-0017."""

    def test_equal(self):
        assert rpmvercmp("1.0", "1.0") == 0

    def test_simple_numeric(self):
        assert rpmvercmp("1.0", "1.1") < 0
        assert rpmvercmp("1.1", "1.0") > 0

    def test_numeric_compares_by_value_not_length(self):
        """1.05 == 1.5 numerically -- leading zeros are stripped before compare."""
        assert rpmvercmp("1.05", "1.5") == 0

    def test_longer_numeric_run_wins_on_tie(self):
        assert rpmvercmp("1.0", "1.0.1") < 0

    def test_extra_trailing_segment_always_wins(self):
        """A string that is a true prefix of the other loses, regardless of
        whether the remaining segment is alpha or numeric -- rpm's real rule
        (e.g. rpm's own test vectors: "2.0.1a" > "2.0.1", "6.0.rc1" > "6.0")."""
        assert rpmvercmp("1.0", "1.0a") < 0
        assert rpmvercmp("1.0a", "1.0") > 0
        assert rpmvercmp("2.0.1", "2.0.1a") < 0

    def test_alpha_run_compared_lexically(self):
        assert rpmvercmp("1.a", "1.b") < 0

    def test_mixed_alpha_numeric_boundary(self):
        assert rpmvercmp("1.a", "1a") == 0

    def test_numeric_beats_alpha_at_same_segment(self):
        """When both sides still have content but one's segment is numeric
        and the other's is alpha at the same position, numeric wins --
        distinct from the trailing-segment rule above (both strings still
        have content left)."""
        assert rpmvercmp("1.5", "1.a5") > 0
        assert rpmvercmp("1.a5", "1.5") < 0

    def test_tilde_sorts_below_everything(self):
        """~ marks a pre-release; it sorts below even the empty/missing segment."""
        assert rpmvercmp("1.0~rc1", "1.0") < 0
        assert rpmvercmp("1.0~rc1", "1.0~rc2") < 0

    def test_caret_sorts_above_missing_segment(self):
        """^ marks a post-release snapshot suffix (this repo's commit versions,
        e.g. "1.2.3^20240101gitabc1234") -- the opposite of ~."""
        assert rpmvercmp("1.0^20240101git", "1.0") > 0


class TestCompareEvr:
    """Test compare_evr against real version-release labels this repo writes
    via lib.version.nvr() into build-report.db's artifacts.version column."""

    def test_release_bump_within_same_version(self):
        assert compare_evr("0.14.2-1.fc44", "0.14.2-2.fc44") < 0

    def test_version_bump_beats_release(self):
        assert compare_evr("0.14.2-2.fc44", "0.15.0-1.fc44") < 0

    def test_trailing_zero_component(self):
        assert compare_evr("1.9-1.fc44", "1.9.0-1.fc44") < 0

    def test_commit_version_vs_plain_version(self):
        """A latest-commit release_type's version string embeds a caret snapshot
        suffix (lib.version.COMMIT_VERSION_RELEASE_TYPES) -- still comparable."""
        assert compare_evr("0.56.0-1.fc44", "0.56.0^20260730git8668a53-1.fc44") < 0

    def test_none_sorts_lowest(self):
        assert compare_evr(None, "1.0.0-1.fc44") < 0
        assert compare_evr("1.0.0-1.fc44", None) > 0
        assert compare_evr(None, None) == 0

    def test_empty_string_sorts_lowest(self):
        assert compare_evr("", "1.0.0-1.fc44") < 0
