"""Tests for COPR module."""

import gzip
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.copr import (
    COPR_BUILD_URL,
    COVERAGE_FAILED,
    COVERAGE_SKIPPED,
    COVERAGE_UNBUILT,
    COVERAGE_UNVERIFIABLE,
    COVERAGE_VERIFIED,
    TERMINAL_STATES,
    blackout_chroots,
    check_copr_credentials,
    chroot_coverage,
    download_chroot_log,
    fetch_failed_chroot_logs,
    get_build_chroots,
    get_project_chroots,
    ineligible_packages,
    parse_build_id,
    poll_copr_status,
    preflight,
    print_chroot_coverage,
    validate_copr_repo,
)

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed_copr(pkg: str, **fields) -> None:
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    state = fields.pop("state", "building")
    build_db.set_stage(pkg, "copr", TARGET, run_id, state, **fields)


class TestParseBuildId:
    """Tests for parse_build_id function."""

    def test_parse_build_id_found(self):
        """Test extracting build ID from valid output."""
        output = """
        Submitting build...
        Created builds: 12345
        Build URL: https://copr.example.com/build/12345
        """
        result = parse_build_id(output)
        assert result == 12345

    def test_parse_build_id_multiple_numbers(self):
        """Test that only the last number on the line is extracted."""
        output = "Created builds: 12345 99999"
        result = parse_build_id(output)
        assert result == 99999

    def test_parse_build_id_not_found(self):
        """Test when 'Created builds:' is not in output."""
        output = """
        Submitting build...
        Build submitted successfully
        """
        result = parse_build_id(output)
        assert result is None

    def test_parse_build_id_malformed_line(self):
        """Test when 'Created builds:' line exists but doesn't have a number."""
        output = "Created builds: none"
        result = parse_build_id(output)
        assert result is None

    def test_parse_build_id_empty_output(self):
        """Test with empty output."""
        result = parse_build_id("")
        assert result is None

    def test_parse_build_id_zero(self):
        """Test with zero build ID."""
        output = "Created builds: 0"
        result = parse_build_id(output)
        assert result == 0


class TestValidateCoprRepo:
    """Tests for validate_copr_repo function."""

    def test_valid_repo_slug(self):
        """Test valid repository slug."""
        assert validate_copr_repo("nett00n/hyprland") is True

    def test_valid_repo_with_dashes(self):
        """Test valid repo with dashes."""
        assert validate_copr_repo("my-org/my-repo") is True

    def test_valid_repo_with_dots(self):
        """Test valid repo with dots."""
        assert validate_copr_repo("org/repo.name") is True

    def test_valid_repo_with_underscores(self):
        """Test valid repo with underscores."""
        assert validate_copr_repo("org_name/repo_name") is True

    def test_invalid_missing_slash(self):
        """Test invalid format without slash."""
        assert validate_copr_repo("nohyphrland") is False

    def test_invalid_multiple_slashes(self):
        """Test invalid format with multiple slashes."""
        assert validate_copr_repo("org/repo/sub") is False

    def test_invalid_empty_parts(self):
        """Test invalid format with empty parts."""
        assert validate_copr_repo("/repo") is False
        assert validate_copr_repo("org/") is False
        assert validate_copr_repo("/") is False

    def test_invalid_special_chars(self):
        """Test invalid format with special characters."""
        assert validate_copr_repo("org@/repo") is False
        assert validate_copr_repo("org/repo#") is False

    def test_empty_string(self):
        """Test empty string."""
        assert validate_copr_repo("") is False


class TestCheckCoprCredentials:
    """Tests for check_copr_credentials function."""

    @patch("lib.copr.run_cmd")
    def test_credentials_valid(self, mock_run_cmd):
        """Test when credentials are valid."""
        mock_run_cmd.return_value = (True, "user: testuser\n", "")

        result = check_copr_credentials()

        assert result is True
        mock_run_cmd.assert_called_once_with(["copr-cli", "whoami"])

    @patch("lib.copr.run_cmd")
    def test_credentials_invalid(self, mock_run_cmd, capsys):
        """Test when credentials are invalid."""
        mock_run_cmd.return_value = (False, "", "Error: unauthorized")

        result = check_copr_credentials()

        assert result is False
        captured = capsys.readouterr()
        assert "invalid or missing" in captured.err
        assert "copr.conf" in captured.err
        assert "Error: unauthorized" in captured.err

    @patch("lib.copr.run_cmd")
    def test_credentials_check_no_stderr(self, mock_run_cmd, capsys):
        """Test error handling without stderr output."""
        mock_run_cmd.return_value = (False, "", "")

        result = check_copr_credentials()

        assert result is False
        captured = capsys.readouterr()
        assert "invalid or missing" in captured.err


class TestPreflight:
    """Tests for preflight function (BUG-0036)."""

    @patch("lib.copr.run_cmd")
    def test_bad_slug_short_circuits_before_credentials_check(self, mock_run_cmd, capsys):
        """An invalid slug must fail without shelling out to copr-cli at all."""
        result = preflight("not-a-slug")

        assert result is False
        mock_run_cmd.assert_not_called()
        captured = capsys.readouterr()
        assert "Invalid COPR_REPO format" in captured.err

    @patch("lib.copr.run_cmd")
    def test_valid_slug_bad_credentials(self, mock_run_cmd):
        mock_run_cmd.return_value = (False, "", "Error: unauthorized")

        assert preflight("nett00n/hyprland") is False

    @patch("lib.copr.run_cmd")
    def test_valid_slug_good_credentials(self, mock_run_cmd):
        mock_run_cmd.return_value = (True, "user: testuser\n", "")

        assert preflight("nett00n/hyprland") is True


class TestPollCoprStatus:
    """Tests for poll_copr_status function."""

    @patch("lib.copr.run_cmd")
    def test_poll_no_packages(self, mock_run_cmd):
        """Test polling with empty package list."""
        result = poll_copr_status(TARGET, [])
        assert result is False
        mock_run_cmd.assert_not_called()

    @patch("lib.copr.run_cmd")
    def test_poll_no_build_id(self, mock_run_cmd):
        """Test polling when package has no build_id."""
        _seed_copr("pkg1", state="pending")
        result = poll_copr_status(TARGET, ["pkg1"])
        assert result is False
        mock_run_cmd.assert_not_called()

    @patch("lib.copr.run_cmd")
    def test_poll_terminal_state_skip(self, mock_run_cmd):
        """Test that terminal states are skipped."""
        _seed_copr("pkg1", build_id=123, state="success")
        _seed_copr("pkg2", build_id=456, state="failed")
        result = poll_copr_status(TARGET, ["pkg1", "pkg2"])
        assert result is False
        mock_run_cmd.assert_not_called()

    @patch("lib.copr.run_cmd")
    def test_poll_status_success(self, mock_run_cmd):
        """Test polling and finding success status."""
        mock_run_cmd.return_value = (True, "Build 123 succeeded", "")

        _seed_copr("pkg1", build_id=123, state="building")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "success"
        mock_run_cmd.assert_called_once_with(["copr-cli", "status", "123"])

    @patch("lib.copr.fetch_failed_chroot_logs")
    @patch("lib.copr.run_cmd")
    def test_poll_status_failed(self, mock_run_cmd, mock_fetch_logs):
        """Test polling and finding failed status."""
        mock_run_cmd.return_value = (True, "Build 456 failed", "")

        _seed_copr("pkg1", build_id=456, state="building")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "failed"
        mock_fetch_logs.assert_called_once_with("pkg1", 456)

    @patch("lib.copr.run_cmd")
    def test_poll_status_no_state_change(self, mock_run_cmd):
        """Test polling when status doesn't change."""
        mock_run_cmd.return_value = (True, "Build 789 succeeded", "")

        _seed_copr("pkg1", build_id=789, state="success")
        result = poll_copr_status(TARGET, ["pkg1"])

        # Status already terminal, should be skipped
        assert result is False
        mock_run_cmd.assert_not_called()

    @patch("lib.copr.run_cmd")
    def test_poll_status_command_failure(self, mock_run_cmd):
        """Test when copr-cli status command fails."""
        mock_run_cmd.return_value = (False, "", "Command failed")

        _seed_copr("pkg1", build_id=999, state="pending")
        result = poll_copr_status(TARGET, ["pkg1"])

        # State should not change on command failure
        assert result is False
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "pending"

    @patch("lib.copr.fetch_failed_chroot_logs")
    @patch("lib.copr.run_cmd")
    def test_poll_multiple_packages(self, mock_run_cmd, mock_fetch_logs):
        """Test polling multiple packages."""
        mock_run_cmd.side_effect = [
            (True, "Build 111 succeeded", ""),
            (True, "Build 222 failed", ""),
        ]

        _seed_copr("pkg1", build_id=111, state="building")
        _seed_copr("pkg2", build_id=222, state="building")
        result = poll_copr_status(TARGET, ["pkg1", "pkg2"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "success"
        assert build_db.get_stage("pkg2", "copr", TARGET)["state"] == "failed"
        mock_fetch_logs.assert_called_once_with("pkg2", 222)

    @patch("lib.copr.run_cmd")
    def test_poll_case_insensitive_status(self, mock_run_cmd):
        """Test that status matching is case-insensitive."""
        mock_run_cmd.return_value = (True, "Build 333 SUCCEEDED", "")

        _seed_copr("pkg1", build_id=333, state="building")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "success"

    @patch("lib.copr.run_cmd")
    def test_poll_no_copr_stage(self, mock_run_cmd):
        """Test polling when there is no copr row at all yet."""
        result = poll_copr_status(TARGET, ["pkg1"])
        assert result is False
        mock_run_cmd.assert_not_called()

    @pytest.mark.parametrize("copr_state", ["canceled", "skipped", "forked"])
    @patch("lib.copr.fetch_failed_chroot_logs")
    @patch("lib.copr.run_cmd")
    def test_poll_status_other_terminal_states_map_to_failed(
        self, mock_run_cmd, mock_fetch_logs, copr_state
    ):
        """BUG-0040: canceled/skipped/forked are terminal but were previously
        never recognized, leaving the row stuck at 'unknown' forever."""
        mock_run_cmd.return_value = (True, copr_state, "")

        _seed_copr("pkg1", build_id=123, state="unknown")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "failed"
        mock_fetch_logs.assert_called_once_with("pkg1", 123)

    @pytest.mark.parametrize(
        "copr_state", ["running", "starting", "pending", "importing", "waiting"]
    )
    @patch("lib.copr.run_cmd")
    def test_poll_status_non_terminal_states_left_alone(self, mock_run_cmd, copr_state):
        """Non-terminal copr-cli states must not be treated as a status change."""
        mock_run_cmd.return_value = (True, copr_state, "")

        _seed_copr("pkg1", build_id=123, state="unknown")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is False
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "unknown"

    @patch("lib.copr.run_cmd")
    def test_poll_status_unrecognized_output_warns_and_leaves_state(
        self, mock_run_cmd, capsys
    ):
        """An unrecognized copr-cli output must not be silently swallowed."""
        mock_run_cmd.return_value = (True, "some future status nobody knows", "")

        _seed_copr("pkg1", build_id=123, state="unknown")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is False
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "unknown"
        captured = capsys.readouterr()
        assert "unrecognized state" in captured.err
        assert "pkg1" in captured.err

    @patch("lib.copr.run_cmd")
    def test_poll_status_rightmost_token_wins(self, mock_run_cmd):
        """BUG-0040: a listing mentioning multiple state words must not
        resolve to whichever one happens to appear first."""
        mock_run_cmd.return_value = (
            True,
            "fedora-44-x86_64 succeeded\nfedora-43-x86_64 failed",
            "",
        )

        _seed_copr("pkg1", build_id=123, state="unknown")
        result = poll_copr_status(TARGET, ["pkg1"])

        assert result is True
        assert build_db.get_stage("pkg1", "copr", TARGET)["state"] == "failed"


CHROOT_LIST_RESPONSE = {
    "items": [
        {
            "name": "fedora-44-x86_64",
            "state": "succeeded",
            "result_url": "https://download.example.com/results/pkg/fedora-44-x86_64/1-pkg/",
        },
        {
            "name": "fedora-43-x86_64",
            "state": "failed",
            "result_url": "https://download.example.com/results/pkg/fedora-43-x86_64/1-pkg/",
        },
    ]
}


class TestGetBuildChroots:
    """Tests for get_build_chroots function."""

    @patch("lib.copr.urllib.request.urlopen")
    def test_parses_items(self, mock_urlopen):
        """Parses the {"items": [...]} shape from the Copr API."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(CHROOT_LIST_RESPONSE).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        chroots = get_build_chroots(10798066)

        assert len(chroots) == 2
        assert chroots[1]["name"] == "fedora-43-x86_64"
        assert chroots[1]["state"] == "failed"
        called_url = mock_urlopen.call_args[0][0]
        assert "10798066" in called_url

    @patch("lib.copr.urllib.request.urlopen")
    def test_url_error_returns_empty(self, mock_urlopen):
        """Network failure returns an empty list instead of raising."""
        mock_urlopen.side_effect = urllib.error.URLError("no network")
        assert get_build_chroots(123) == []

    @patch("lib.copr.urllib.request.urlopen")
    def test_malformed_json_returns_empty(self, mock_urlopen):
        """Malformed JSON returns an empty list instead of raising."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        assert get_build_chroots(123) == []


PROJECT_RESPONSE_CHROOT_REPOS = {
    "chroot_repos": {
        "fedora-43-x86_64": "https://example.com/results/fedora-43-x86_64/",
        "fedora-43-aarch64": "https://example.com/results/fedora-43-aarch64/",
        "fedora-44-x86_64": "https://example.com/results/fedora-44-x86_64/",
        "fedora-44-aarch64": "https://example.com/results/fedora-44-aarch64/",
        "fedora-rawhide-x86_64": "https://example.com/results/fedora-rawhide-x86_64/",
        "fedora-rawhide-aarch64": "https://example.com/results/fedora-rawhide-aarch64/",
    }
}


class TestGetProjectChroots:
    """Tests for get_project_chroots function."""

    @patch("lib.copr.urllib.request.urlopen")
    def test_parses_chroot_repos_dict(self, mock_urlopen):
        """Parses the live API shape: chroot_repos is a dict keyed by chroot name."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            PROJECT_RESPONSE_CHROOT_REPOS
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        chroots = get_project_chroots("nett00n/hyprland")

        assert chroots == sorted(PROJECT_RESPONSE_CHROOT_REPOS["chroot_repos"])
        called_url = mock_urlopen.call_args[0][0]
        assert "ownername=nett00n" in called_url
        assert "projectname=hyprland" in called_url

    @patch("lib.copr.urllib.request.urlopen")
    def test_parses_chroots_list_fallback_shape(self, mock_urlopen):
        """Tolerates a hypothetical {"chroots": [...]} list shape too."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"chroots": ["fedora-44-x86_64", "fedora-43-x86_64"]}
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        assert get_project_chroots("nett00n/hyprland") == [
            "fedora-43-x86_64",
            "fedora-44-x86_64",
        ]

    @patch("lib.copr.urllib.request.urlopen")
    def test_url_error_returns_empty(self, mock_urlopen):
        """Network failure returns an empty list instead of raising."""
        mock_urlopen.side_effect = urllib.error.URLError("no network")
        assert get_project_chroots("nett00n/hyprland") == []

    @patch("lib.copr.urllib.request.urlopen")
    def test_malformed_json_returns_empty(self, mock_urlopen):
        """Malformed JSON returns an empty list instead of raising."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        assert get_project_chroots("nett00n/hyprland") == []

    def test_invalid_slug_returns_empty_without_network(self):
        """Invalid owner/project slug is rejected before any request is made."""
        assert get_project_chroots("not-a-valid-slug") == []


class TestChrootCoverage:
    """Tests for chroot_coverage function."""

    def _set_mock(self, pkg: str, chroot: str, state: str) -> None:
        run_id = build_db.start_run(chroot, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "mock", chroot, run_id, state)

    def test_verified_when_mock_succeeded(self):
        self._set_mock("hyprutils", "fedora-44-x86_64", "success")
        result = chroot_coverage("hyprutils", ["fedora-44-x86_64"])
        assert result == {"fedora-44-x86_64": COVERAGE_VERIFIED}

    def test_failed_when_mock_failed(self):
        self._set_mock("hyprutils", "fedora-43-x86_64", "failed")
        result = chroot_coverage("hyprutils", ["fedora-43-x86_64"])
        assert result == {"fedora-43-x86_64": COVERAGE_FAILED}

    def test_unbuilt_when_no_mock_row(self):
        result = chroot_coverage("hyprutils", ["fedora-44-x86_64"])
        assert result == {"fedora-44-x86_64": COVERAGE_UNBUILT}

    def test_unverifiable_for_different_arch(self):
        """aarch64 chroots are never locally buildable -- see TODO-0024."""
        result = chroot_coverage("hyprutils", ["fedora-44-aarch64"])
        assert result == {"fedora-44-aarch64": COVERAGE_UNVERIFIABLE}

    def test_mixed_chroots(self):
        self._set_mock("hyprutils", "fedora-44-x86_64", "success")
        self._set_mock("hyprutils", "fedora-43-x86_64", "failed")
        result = chroot_coverage(
            "hyprutils",
            ["fedora-44-x86_64", "fedora-43-x86_64", "fedora-rawhide-x86_64", "fedora-44-aarch64"],
        )
        assert result == {
            "fedora-44-x86_64": COVERAGE_VERIFIED,
            "fedora-43-x86_64": COVERAGE_FAILED,
            # rawhide is no longer in SUPPORTED_FEDORA_VERSIONS/local_chroots()
            # -- a Copr project that still lists it (or any other chroot this
            # host's matrix doesn't cover) is UNVERIFIABLE, not UNBUILT, so it
            # can never permanently block a submission (see
            # chroot_coverage()'s docstring for the deadlock this avoids).
            "fedora-rawhide-x86_64": COVERAGE_UNVERIFIABLE,
            "fedora-44-aarch64": COVERAGE_UNVERIFIABLE,
        }

    def test_skipped_when_mock_configured_skip(self):
        """A deliberate packages.yaml `fedora: '<ver>': skip: true` (stage-mock.py
        writes state=skipped, reason="config: skip") must count the same as a
        verified build -- it's an intentional opt-out, not a gap. See
        docs/packaging.md "Per-Fedora-version spec differences"."""
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage(
            "hyprutils", "mock", "fedora-43-x86_64", run_id, "skipped",
            reason="config: skip",
        )
        result = chroot_coverage("hyprutils", ["fedora-43-x86_64"])
        assert result == {"fedora-43-x86_64": COVERAGE_SKIPPED}

    def test_unbuilt_when_skipped_for_other_reason(self):
        """A "skipped" mock row for any other reason (e.g. srpm-stage failure
        cascading downstream) must not be mistaken for a deliberate opt-out."""
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage(
            "hyprutils", "mock", "fedora-43-x86_64", run_id, "skipped",
            reason="srpm failed",
        )
        result = chroot_coverage("hyprutils", ["fedora-43-x86_64"])
        assert result == {"fedora-43-x86_64": COVERAGE_UNBUILT}


class TestPrintChrootCoverage:
    """Tests for print_chroot_coverage function."""

    @patch("lib.copr.get_project_chroots")
    def test_all_verified_returns_true(self, mock_chroots):
        mock_chroots.return_value = ["fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is True

    @patch("lib.copr.get_project_chroots")
    def test_unbuilt_same_arch_returns_false(self, mock_chroots):
        """A same-arch chroot nobody has built locally yet should block strict mode."""
        mock_chroots.return_value = ["fedora-44-x86_64"]
        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is False

    @patch("lib.copr.get_project_chroots")
    def test_aarch64_only_gap_returns_true(self, mock_chroots):
        """An aarch64-only gap must never flip the return to False -- there is no
        local way to close it (TODO-0024), so it can't gate a submission."""
        mock_chroots.return_value = ["fedora-44-aarch64"]
        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is True

    @patch("lib.copr.get_project_chroots")
    def test_api_failure_falls_back_to_supported_versions(self, mock_chroots):
        """When the Copr API is unreachable, falls back to x86_64 chroots derived
        from SUPPORTED_FEDORA_VERSIONS rather than reporting no coverage gap at all."""
        mock_chroots.return_value = []
        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is False

    @patch("lib.copr.get_project_chroots")
    def test_zero_coverage_chroot_prints_blackout_line(self, mock_chroots, capsys):
        """A locally-buildable chroot with no verified/skipped package must be
        called out explicitly, not just folded into the generic '0 verified'
        count -- this is the BUG-0051 case: every package will be held back."""
        mock_chroots.return_value = ["fedora-44-x86_64"]
        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is False
        out = capsys.readouterr().out
        assert "zero local coverage" in out
        assert "matrix-chroot-<version>" in out

    @patch("lib.copr.get_project_chroots")
    def test_aarch64_only_gap_has_no_blackout_line(self, mock_chroots, capsys):
        """An unverifiable-only gap must not be reported as a blackout -- there's
        no local way to close it, so it can't be actionable advice."""
        mock_chroots.return_value = ["fedora-44-aarch64"]
        assert print_chroot_coverage("nett00n/hyprland", {"hyprutils": {}}) is True
        out = capsys.readouterr().out
        assert "zero local coverage" not in out

    @patch("lib.copr.get_project_chroots")
    def test_partial_coverage_has_no_blackout_line(self, mock_chroots, capsys):
        """One of two packages verified on a chroot is the per-package gate
        working as designed, not a blackout -- must stay quiet (though the
        generic "some chroots have no verified" advice still fires, since
        hyprlang is unbuilt there)."""
        mock_chroots.return_value = ["fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert (
            print_chroot_coverage(
                "nett00n/hyprland", {"hyprutils": {}, "hyprlang": {}}
            )
            is False
        )
        out = capsys.readouterr().out
        assert "zero local coverage" not in out


class TestBlackoutChroots:
    """Tests for blackout_chroots() -- the chroots that would hold back every
    package this run (docs/bugs.md BUG-0051)."""

    @patch("lib.copr.get_project_chroots")
    def test_zero_coverage_chroot_is_a_blackout(self, mock_chroots):
        mock_chroots.return_value = ["fedora-44-x86_64"]
        assert blackout_chroots("nett00n/hyprland", {"hyprutils": {}}) == [
            "fedora-44-x86_64"
        ]

    @patch("lib.copr.get_project_chroots")
    def test_verified_chroot_is_not_a_blackout(self, mock_chroots):
        mock_chroots.return_value = ["fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert blackout_chroots("nett00n/hyprland", {"hyprutils": {}}) == []

    @patch("lib.copr.get_project_chroots")
    def test_aarch64_only_gap_is_not_a_blackout(self, mock_chroots):
        """Unverifiable chroots can never be closed locally, so they must never
        appear in the blackout list (that would make the gate un-satisfiable)."""
        mock_chroots.return_value = ["fedora-44-aarch64"]
        assert blackout_chroots("nett00n/hyprland", {"hyprutils": {}}) == []

    @patch("lib.copr.get_project_chroots")
    def test_partial_coverage_is_not_a_blackout(self, mock_chroots):
        mock_chroots.return_value = ["fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert (
            blackout_chroots("nett00n/hyprland", {"hyprutils": {}, "hyprlang": {}})
            == []
        )

    @patch("lib.copr.get_project_chroots")
    def test_no_packages_is_not_a_blackout(self, mock_chroots):
        mock_chroots.return_value = ["fedora-44-x86_64"]
        assert blackout_chroots("nett00n/hyprland", {}) == []


class TestIneligiblePackages:
    """Per-package Copr submission gate (docs/CHANGELOG.md, docs/FRD.md
    COPR-0017): a package is eligible once every chroot in `local_chroots()`
    that the Copr project actually builds is verified or a deliberate skip.
    """

    @patch("lib.copr.get_project_chroots")
    def test_verified_everywhere_is_eligible(self, mock_chroots):
        mock_chroots.return_value = ["fedora-43-x86_64", "fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-43-x86_64", run_id, "success")
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert ineligible_packages("nett00n/hyprland", {"hyprutils": {}}) == {}

    @patch("lib.copr.get_project_chroots")
    def test_failed_on_one_chroot_is_ineligible(self, mock_chroots):
        mock_chroots.return_value = ["fedora-43-x86_64", "fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-43-x86_64", run_id, "success")
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "failed")

        reasons = ineligible_packages("nett00n/hyprland", {"hyprutils": {}})

        assert "hyprutils" in reasons
        assert "fedora-44-x86_64" in reasons["hyprutils"]

    @patch("lib.copr.get_project_chroots")
    def test_unbuilt_chroot_is_ineligible(self, mock_chroots):
        """Never having run mock at all for a chroot blocks the same as failing it."""
        mock_chroots.return_value = ["fedora-43-x86_64", "fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-43-x86_64", run_id, "success")

        reasons = ineligible_packages("nett00n/hyprland", {"hyprutils": {}})

        assert "fedora-44-x86_64" in reasons["hyprutils"]

    @patch("lib.copr.get_project_chroots")
    def test_config_skipped_chroot_is_eligible(self, mock_chroots):
        """A deliberate packages.yaml skip counts as clear, not a gap."""
        mock_chroots.return_value = ["fedora-43-x86_64", "fedora-44-x86_64"]
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage(
            "hyprutils", "mock", "fedora-43-x86_64", run_id, "skipped",
            reason="config: skip",
        )
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert ineligible_packages("nett00n/hyprland", {"hyprutils": {}}) == {}

    @patch("lib.copr.get_project_chroots")
    def test_aarch64_gap_is_eligible(self, mock_chroots):
        """aarch64 is never in local_chroots() -- it can never block (TODO-0024)."""
        mock_chroots.return_value = ["fedora-44-x86_64", "fedora-44-aarch64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert ineligible_packages("nett00n/hyprland", {"hyprutils": {}}) == {}

    @patch("lib.copr.get_project_chroots")
    def test_copr_chroot_outside_local_matrix_never_blocks(self, mock_chroots):
        """The deadlock this specifically avoids: a Copr project still listing
        a chroot this host's SUPPORTED_FEDORA_VERSIONS no longer builds (e.g.
        a leftover fedora-rawhide-x86_64) must never make every package
        ineligible forever -- there is no local mock row that could ever
        satisfy it."""
        mock_chroots.return_value = ["fedora-44-x86_64", "fedora-rawhide-x86_64"]
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id, "success")

        assert ineligible_packages("nett00n/hyprland", {"hyprutils": {}}) == {}


class TestDownloadChrootLog:
    """Tests for download_chroot_log function."""

    @patch("lib.copr.urllib.request.urlopen")
    def test_downloads_and_decompresses(self, mock_urlopen, tmp_path):
        """Fetches builder-live.log.gz and writes the decompressed content."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = gzip.compress(b"line one\nline two\n")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dest = tmp_path / "31-copr-fedora-43-x86_64.log"
        result = download_chroot_log("https://example.com/results/", dest)

        assert result is True
        assert dest.read_text() == "line one\nline two\n"
        called_url = mock_urlopen.call_args[0][0]
        assert called_url == "https://example.com/results/builder-live.log.gz"

    @patch("lib.copr.urllib.request.urlopen")
    def test_falls_back_to_build_log(self, mock_urlopen, tmp_path):
        """Falls back to build.log.gz when builder-live.log.gz 404s."""
        ok_resp = MagicMock()
        ok_resp.read.return_value = gzip.compress(b"fallback content\n")
        mock_urlopen.side_effect = [
            urllib.error.URLError("404"),
            MagicMock(__enter__=MagicMock(return_value=ok_resp), __exit__=MagicMock()),
        ]

        dest = tmp_path / "log.log"
        result = download_chroot_log("https://example.com/results", dest)

        assert result is True
        assert dest.read_text() == "fallback content\n"

    @patch("lib.copr.urllib.request.urlopen")
    def test_returns_false_when_all_candidates_fail(self, mock_urlopen, tmp_path):
        """Returns False without writing dest when nothing is fetchable."""
        mock_urlopen.side_effect = urllib.error.URLError("gone")
        dest = tmp_path / "log.log"

        result = download_chroot_log("https://example.com/results/", dest)

        assert result is False
        assert not dest.exists()


class TestFetchFailedChrootLogs:
    """Tests for fetch_failed_chroot_logs function."""

    @patch("lib.copr.download_chroot_log")
    @patch("lib.copr.get_build_chroots")
    def test_writes_summary_and_downloads_only_failed(
        self, mock_get_chroots, mock_download, tmp_path, monkeypatch
    ):
        """Writes 30-copr-chroots.log for all chroots, downloads only failed ones."""
        monkeypatch.setattr(paths, "BUILD_LOG_DIR", tmp_path)
        mock_get_chroots.return_value = CHROOT_LIST_RESPONSE["items"]
        mock_download.return_value = True

        fetch_failed_chroot_logs("hyprland-git", 10798066)

        summary = (tmp_path / "hyprland-git" / "30-copr-chroots.log").read_text()
        assert "fedora-44-x86_64 succeeded" in summary
        assert "fedora-43-x86_64 failed" in summary
        mock_download.assert_called_once_with(
            CHROOT_LIST_RESPONSE["items"][1]["result_url"],
            tmp_path / "hyprland-git" / "31-copr-fedora-43-x86_64.log",
        )

    @patch("lib.copr.get_build_chroots")
    def test_no_chroots_writes_nothing(self, mock_get_chroots, tmp_path, monkeypatch):
        """Empty chroot list (e.g. API failure) writes no files."""
        monkeypatch.setattr(paths, "BUILD_LOG_DIR", tmp_path)
        mock_get_chroots.return_value = []

        fetch_failed_chroot_logs("pkg", 1)

        assert not (tmp_path / "pkg").exists()

    @patch("lib.copr.get_build_chroots")
    def test_never_raises(self, mock_get_chroots):
        """Any unexpected exception is swallowed -- this must never break polling."""
        mock_get_chroots.side_effect = RuntimeError("boom")
        fetch_failed_chroot_logs("pkg", 1)  # should not raise
