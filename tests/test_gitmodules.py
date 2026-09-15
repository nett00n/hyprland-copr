"""Tests for gitmodules module."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.lib.gitmodules import (
    ensure_initialized,
    fetch_tags,
    get_changelog_info,
    get_commit_info,
    get_submodule_commit,
    get_submodule_commit_with_base,
    get_tag_commit,
    get_tag_info,
    parse_gitmodules,
    resolve_module,
)


def _cp(returncode=0, stdout="", stderr=""):
    """Build a CompletedProcess the way run_git() would return it."""
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


class TestParseGitmodules:
    """Tests for parse_gitmodules function."""

    def test_parse_empty_gitmodules(self):
        """Test parsing empty .gitmodules file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitmodules = Path(tmpdir) / ".gitmodules"
            gitmodules.write_text("")
            result = parse_gitmodules(gitmodules)
            assert result == []

    def test_parse_single_submodule(self):
        """Test parsing .gitmodules with single submodule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitmodules = Path(tmpdir) / ".gitmodules"
            gitmodules.write_text(
                '[submodule "hyprland"]\n'
                "\tpath = submodules/hyprwm/hyprland\n"
                "\turl = https://github.com/hyprwm/hyprland.git\n"
            )
            result = parse_gitmodules(gitmodules)
            assert len(result) == 1
            assert result[0]["name"] == "hyprland"
            assert result[0]["path"] == "submodules/hyprwm/hyprland"
            assert result[0]["url"] == "https://github.com/hyprwm/hyprland.git"

    def test_parse_multiple_submodules(self):
        """Test parsing .gitmodules with multiple submodules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitmodules = Path(tmpdir) / ".gitmodules"
            gitmodules.write_text(
                '[submodule "pkg1"]\n'
                "\tpath = submodules/org/pkg1\n"
                "\turl = https://github.com/org/pkg1.git\n"
                '[submodule "pkg2"]\n'
                "\tpath = submodules/org/pkg2\n"
                "\turl = https://github.com/org/pkg2.git\n"
            )
            result = parse_gitmodules(gitmodules)
            assert len(result) == 2
            assert result[0]["name"] == "pkg1"
            assert result[1]["name"] == "pkg2"

    def test_parse_submodule_missing_fields(self):
        """Test parsing submodule with missing optional fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitmodules = Path(tmpdir) / ".gitmodules"
            gitmodules.write_text('[submodule "incomplete"]\n')
            result = parse_gitmodules(gitmodules)
            assert len(result) == 1
            assert result[0]["name"] == "incomplete"
            assert result[0]["path"] == ""
            assert result[0]["url"] == ""


class TestFetchTags:
    """Tests for fetch_tags function."""

    @patch("scripts.lib.gitmodules.run_git")
    def test_fetch_tags_success(self, mock_run):
        """Test successful tag fetch."""
        mock_run.return_value = _cp(
            returncode=0,
            stdout=(
                "abc123\trefs/tags/v1.0.0\n"
                "def456\trefs/tags/v2.0.0\n"
                "ghi789\trefs/tags/v2.0.0^{}\n"
            ),
        )

        result = fetch_tags("https://github.com/hyprwm/hyprland.git")

        assert "v1.0.0" in result
        assert "v2.0.0" in result
        # Dereferenced tag (^{}) should not be in results
        assert not any("^{}" in tag for tag in result)

    @patch("scripts.lib.gitmodules.run_git")
    def test_fetch_tags_command_failure(self, mock_run, capsys):
        """Test handling of git command failure."""
        mock_run.return_value = _cp(returncode=128, stdout="")

        result = fetch_tags("https://invalid.git")

        assert result == []
        captured = capsys.readouterr()
        assert "warning" in captured.err

    @patch("scripts.lib.gitmodules.run_git")
    def test_fetch_tags_timeout(self, mock_run, capsys):
        """Test handling of timeout (run_git reports it as returncode=124)."""
        mock_run.return_value = _cp(
            returncode=124, stdout="", stderr="command timed out after 30s: git ls-remote"
        )

        result = fetch_tags("https://slow-repo.git")

        assert result == []
        captured = capsys.readouterr()
        assert "warning" in captured.err
        assert "timeout" in captured.err

    @patch("scripts.lib.gitmodules.run_git")
    def test_fetch_tags_malformed_output(self, mock_run):
        """Test handling of malformed output."""
        mock_run.return_value = _cp(
            returncode=0,
            stdout=(
                "malformed line\n"
                "abc123\trefs/tags/v1.0.0\n"
                "another bad line\n"
            ),
        )

        result = fetch_tags("https://example.com/repo.git")

        # Should only have the properly formatted line
        assert "v1.0.0" in result


class TestEnsureInitialized:
    """Tests for ensure_initialized function."""

    def test_no_matching_urls_returns_empty(self):
        """No module matches urls -> no subprocess calls, empty result."""
        modules = [{"path": "submodules/org/pkg1", "url": "https://x/pkg1.git"}]
        assert ensure_initialized(Path("/repo"), modules, {"https://x/other.git"}) == []

    @patch("scripts.lib.gitmodules.run_git")
    def test_status_failure_returns_empty(self, mock_run):
        """`git submodule status` failing (e.g. timeout) yields [] rather than raising."""
        mock_run.return_value = _cp(returncode=124, stderr="command timed out after 300s")
        modules = [{"path": "submodules/org/pkg1", "url": "https://x/pkg1.git"}]

        result = ensure_initialized(Path("/repo"), modules, {"https://x/pkg1.git"})

        assert result == []

    @patch("scripts.lib.gitmodules.run_git")
    def test_already_initialized_returns_empty(self, mock_run):
        """No leading '-' lines -> nothing to init, update is never called."""
        mock_run.return_value = _cp(returncode=0, stdout=" abc123 submodules/org/pkg1 (v1.0)\n")
        modules = [{"path": "submodules/org/pkg1", "url": "https://x/pkg1.git"}]

        result = ensure_initialized(Path("/repo"), modules, {"https://x/pkg1.git"})

        assert result == []
        mock_run.assert_called_once()  # only the status call

    @patch("scripts.lib.gitmodules.run_git")
    def test_initializes_uninitialized_submodule(self, mock_run):
        """A leading '-' line triggers `submodule update --init` for that path."""
        status = _cp(returncode=0, stdout="-0000000000000000000000000000000000000000 submodules/org/pkg1\n")
        update = _cp(returncode=0)
        mock_run.side_effect = [status, update]
        modules = [{"path": "submodules/org/pkg1", "url": "https://x/pkg1.git"}]

        result = ensure_initialized(Path("/repo"), modules, {"https://x/pkg1.git"})

        assert result == ["submodules/org/pkg1"]
        assert mock_run.call_count == 2

    @patch("scripts.lib.gitmodules.run_git")
    def test_update_failure_raises(self, mock_run):
        """`submodule update --init` failing must fail loud, not silently return []."""
        status = _cp(returncode=0, stdout="-0000000000000000000000000000000000000000 submodules/org/pkg1\n")
        update = _cp(returncode=1, stderr="fatal: unable to fetch")
        mock_run.side_effect = [status, update]
        modules = [{"path": "submodules/org/pkg1", "url": "https://x/pkg1.git"}]

        with pytest.raises(RuntimeError, match="unable to fetch"):
            ensure_initialized(Path("/repo"), modules, {"https://x/pkg1.git"})


class TestResolveModule:
    """Tests for resolve_module function."""

    def test_resolve_module_found(self):
        """Test finding a module by name."""
        modules = [
            {"name": "hyprland", "path": "submodules/hyprwm/hyprland", "url": "..."},
            {"name": "hyprpicker", "path": "submodules/hyprwm/hyprpicker", "url": "..."},
        ]
        result = resolve_module(modules, "hyprland")
        assert result is not None
        assert result["name"] == "hyprland"

    def test_resolve_module_case_insensitive(self):
        """Test that resolution is case-insensitive."""
        modules = [
            {"name": "Hyprland", "path": "submodules/hyprwm/Hyprland", "url": "..."},
        ]
        result = resolve_module(modules, "hyprland")
        assert result is not None

    def test_resolve_module_not_found(self):
        """Test when module is not found."""
        modules = [
            {"name": "pkg1", "path": "submodules/org/pkg1", "url": "..."},
        ]
        result = resolve_module(modules, "nonexistent")
        assert result is None

    def test_resolve_module_empty_list(self):
        """Test with empty module list."""
        result = resolve_module([], "anything")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_info_not_found(mock_run):
    """Test get_tag_info when tag doesn't exist."""
    mock_run.return_value = _cp(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_info_with_lightweight_tag(mock_run):
    """Test get_tag_info with lightweight tag (no annotated info)."""
    # First call: git tag -l (tag exists)
    check1 = _cp(returncode=0, stdout="v1.0.0\n")
    # Second call: git cat-file tag (lightweight tag, fails)
    cat = _cp(returncode=1, stdout="")
    # Third call: git log (fallback for date/body)
    log = _cp(returncode=0, stdout="2024-01-01T00:00:00+00:00\nRelease v1.0.0\n")
    # Fourth call: git rev-list for commit hash
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check1, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        assert result["tag"] == "v1.0.0"
        assert "2024-01-01" in result["published_at"]
        assert result["body"] == "Release v1.0.0"
        assert result["commit"] == "abc123def456"


@patch("scripts.lib.gitmodules.run_git")
def test_get_commit_info_success(mock_run):
    """Test get_commit_info with valid commit."""
    mock_run.return_value = _cp(
        returncode=0,
        stdout="abc123def456\n2024-01-01T00:00:00+00:00\nCommit message\nwith body\n",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is not None
        assert result["commit"] == "abc123def456"
        assert "2024-01-01" in result["published_at"]
        assert "Commit message" in result["body"]


@patch("scripts.lib.gitmodules.run_git")
def test_get_commit_info_failure(mock_run):
    """Test get_commit_info when git command fails."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "invalid")
        assert result is None


@patch("scripts.lib.gitmodules.get_commit_info")
@patch("scripts.lib.gitmodules.get_tag_info")
def test_get_changelog_info_tag_preferred(mock_tag_info, mock_commit_info):
    """Test that get_changelog_info prefers tag over commit."""
    mock_tag_info.return_value = {
        "published_at": "2024-01-01T00:00:00+00:00",
        "body": "Tag release",
        "tag": "v1.0.0",
        "commit": "abc123",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "def456")
        assert result["tag"] == "v1.0.0"
        # commit_info should not be called since tag exists
        mock_commit_info.assert_not_called()


@patch("scripts.lib.gitmodules.get_commit_info")
@patch("scripts.lib.gitmodules.get_tag_info")
def test_get_changelog_info_fallback_to_commit(mock_tag_info, mock_commit_info):
    """Test that get_changelog_info falls back to commit."""
    mock_tag_info.return_value = None
    mock_commit_info.return_value = {
        "published_at": "2024-01-01T00:00:00+00:00",
        "body": "Commit message",
        "commit": "def456",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "def456")
        assert result["commit"] == "def456"
        assert "Commit message" in result["body"]


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_success(mock_run):
    """Test get_submodule_commit with valid commit."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit(Path(tmpdir))
        assert result is not None
        assert result[0] == "abc123def456"  # full hash
        assert result[1] == "abc123d"  # short hash
        assert result[2] == "20240101"  # date


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_failure(mock_run):
    """Test get_submodule_commit with command failure (e.g. a timeout)."""
    mock_run.return_value = _cp(returncode=124, stderr="command timed out after 300s")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit(Path(tmpdir))
        assert result is None


@patch("scripts.lib.gitmodules.get_submodule_commit")
@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_with_base_success(mock_run, mock_get_commit):
    """Test get_submodule_commit_with_base finds base semver."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=0, stdout="v1.5.0\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit_with_base(Path(tmpdir))
        assert result is not None
        assert result[0] == "abc123def456"
        assert result[3] == "1.5.0"  # v-prefix stripped


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_accepts_ref(mock_run):
    """A ref other than HEAD (e.g. origin/<branch>) must reach `git log`, so
    version resolution doesn't depend on the working tree's checked-out
    commit (see docs/BUGS.md BUG-0033)."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        get_submodule_commit(Path(tmpdir), ref="origin/main")

    argv = mock_run.call_args[0]
    assert argv[-1] == "origin/main"


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_defaults_to_head(mock_run):
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        get_submodule_commit(Path(tmpdir))

    argv = mock_run.call_args[0]
    assert argv[-1] == "HEAD"


@patch("scripts.lib.gitmodules.get_submodule_commit")
@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_with_base_threads_ref(mock_run, mock_get_commit):
    """get_submodule_commit_with_base must pass `ref` through to
    get_submodule_commit, and describe the nearest semver tag from the
    *resolved commit hash* rather than the literal ref -- so it can't
    disagree with get_submodule_commit if a remote-tracking ref moves
    between the two subprocess calls."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=0, stdout="v1.5.0\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit_with_base(Path(tmpdir), ref="origin/main")

    mock_get_commit.assert_called_once_with(Path(tmpdir), "origin/main")
    describe_argv = mock_run.call_args[0]
    assert describe_argv[-1] == "abc123def456"
    assert result[3] == "1.5.0"


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_commit_success(mock_run):
    """Test get_tag_commit with valid tag."""
    rev = _cp(returncode=0, stdout="abc123def456\n")
    date_result = _cp(returncode=0, stdout="20240101\n")
    describe = _cp(returncode=0, stdout="v1.5.0\n")

    mock_run.side_effect = [rev, date_result, describe]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v2.0.0")
        assert result is not None
        assert result[0] == "abc123def456"
        assert result[1] == "abc123d"
        assert result[2] == "20240101"
        assert result[3] == "1.5.0"


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_commit_invalid_tag(mock_run):
    """Test get_tag_commit with invalid tag."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "invalid")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_info_with_tagger_timestamp(mock_run):
    """Test extracting timestamp from tagger line."""
    check = _cp(returncode=0, stdout="v1.0.0\n")
    cat = _cp(
        returncode=0,
        stdout=(
            "object abc123\n"
            "type commit\n"
            "tag v1.0.0\n"
            "tagger John Doe <john@example.com> 1704067200 +0000\n"
            "\n"
            "Release\n"
        ),
    )
    log = _cp(returncode=1, stdout="")
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        # Verify timestamp was parsed
        assert "2024-01-01" in result["published_at"]


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_info_no_tagger_uses_log(mock_run):
    """Test fallback to log when tagger line missing."""
    check = _cp(returncode=0, stdout="v1.0.0\n")
    cat = _cp(returncode=0, stdout="object abc123\ntype commit\n\n")
    log = _cp(returncode=0, stdout="2024-01-01T10:00:00+00:00\nRelease message\n")
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        assert "2024-01-01" in result["published_at"]


@patch("scripts.lib.gitmodules.run_git")
def test_get_commit_info_invalid_date(mock_run):
    """Test get_commit_info with invalid ISO date."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123\ninvalid-date\nbody\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_commit_info_missing_fields(mock_run):
    """Test get_commit_info with missing fields."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123\n")  # missing date and body

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is None


@patch("scripts.lib.gitmodules.get_commit_info")
@patch("scripts.lib.gitmodules.get_tag_info")
def test_get_changelog_info_no_tag_no_commit(mock_tag_info, mock_commit_info):
    """Test get_changelog_info when both tag and commit fail."""
    mock_tag_info.return_value = None
    mock_commit_info.return_value = None

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "abc123")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_with_multiple_fields(mock_run):
    """Test get_submodule_commit with output containing multiple fields."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101 extra stuff\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit(Path(tmpdir))
        assert result is not None
        # Should use first two parts
        assert result[0] == "abc123def456"
        assert result[2] == "20240101"


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_empty_output(mock_run):
    """Test get_submodule_commit with empty output."""
    mock_run.return_value = _cp(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit(Path(tmpdir))
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_with_base_no_commit(mock_run):
    """Test get_submodule_commit_with_base when commit call fails."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit_with_base(Path(tmpdir))
        assert result is None


@patch("scripts.lib.gitmodules.get_submodule_commit")
@patch("scripts.lib.gitmodules.run_git")
def test_get_submodule_commit_with_base_no_semver(mock_run, mock_get_commit):
    """Test get_submodule_commit_with_base when no semver tag found."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=128, stdout="")  # tag not found

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_submodule_commit_with_base(Path(tmpdir))
        assert result is not None
        assert result[3] is None  # base_semver should be None


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_commit_date_failure(mock_run):
    """Test get_tag_commit when date retrieval fails."""
    rev = _cp(returncode=0, stdout="abc123def456\n")
    date_result = _cp(returncode=1, stdout="")

    mock_run.side_effect = [rev, date_result]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v1.0.0")
        assert result is None


@patch("scripts.lib.gitmodules.run_git")
def test_get_tag_commit_with_timeout(mock_run):
    """A run_git timeout (returncode=124) on the first call must not raise."""
    mock_run.return_value = _cp(returncode=124, stderr="command timed out after 10s")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v1.0.0")
        assert result is None
