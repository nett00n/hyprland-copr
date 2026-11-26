"""Tests for tarball module."""

from unittest.mock import MagicMock, patch


from scripts.lib.tarball import detect_tarball_source_name


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_matches_expected(mock_popen, mock_run):
    """Test when tarball top-level dir matches expected format."""
    # Setup: tarball contains pkg-version at top level
    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "pkg-1.0.0/file.txt\npkg-1.0.0/dir/file2.txt"
    mock_run.return_value = mock_result

    result = detect_tarball_source_name(
        ["https://example.com/archive.tar.gz"], "pkg", "1.0.0"
    )

    # Should return None when it matches expected format
    assert result is None


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_different_directory(mock_popen, mock_run):
    """Test when tarball top-level dir differs from expected format."""
    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Waybar-0.9.0/file.txt\nWaybar-0.9.0/dir/file2.txt"
    mock_run.return_value = mock_result

    result = detect_tarball_source_name(
        ["https://example.com/archive.tar.gz"], "waybar", "0.9.0"
    )

    # Should return "Waybar" since it differs from "waybar-0.9.0"
    assert result == "Waybar"


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_strips_version_suffix(mock_popen, mock_run):
    """Test that version suffix is stripped from directory name."""
    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "proj-1.5.2/file.txt"
    mock_run.return_value = mock_result

    result = detect_tarball_source_name(
        ["https://example.com/archive.tar.gz"], "pkg", "1.5.2"
    )

    # Should strip "1.5.2" suffix and return "proj"
    assert result == "proj"


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_tries_multiple_urls(mock_popen, mock_run):
    """Test that function tries multiple URLs until one succeeds."""
    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None

    # First URL fails, second succeeds
    mock_result_fail = MagicMock()
    mock_result_fail.returncode = 1
    mock_result_success = MagicMock()
    mock_result_success.returncode = 0
    mock_result_success.stdout = "Archive-1.0/file.txt"

    mock_run.side_effect = [mock_result_fail, mock_result_success]

    result = detect_tarball_source_name(
        ["https://example.com/fail.tar.gz", "https://example.com/success.tar.gz"],
        "archive",
        "1.0",
    )

    assert result == "Archive"
    assert mock_popen.call_count == 2


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_all_urls_fail(mock_popen, mock_run):
    """Test when all URLs fail to fetch."""
    import subprocess

    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None
    mock_curl.wait.side_effect = subprocess.TimeoutExpired("curl", 30)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_run.return_value = mock_result

    result = detect_tarball_source_name(
        ["https://example.com/fail1.tar.gz", "https://example.com/fail2.tar.gz"],
        "pkg",
        "1.0",
    )

    # Should return None when all fail
    assert result is None


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_no_dash_in_directory(mock_popen, mock_run):
    """Test handling of directory name with no dashes."""
    mock_curl = MagicMock()
    mock_popen.return_value = mock_curl
    mock_curl.stdout = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "SingleName/file.txt"
    mock_run.return_value = mock_result

    result = detect_tarball_source_name(
        ["https://example.com/archive.tar.gz"], "pkg", "1.0"
    )

    # Should return "SingleName" (no dash to strip)
    assert result == "SingleName"


@patch("scripts.lib.tarball.subprocess.run")
@patch("scripts.lib.tarball.subprocess.Popen")
def test_detect_tarball_source_name_empty_url_list(mock_popen, mock_run):
    """Test with empty URL list."""
    result = detect_tarball_source_name([], "pkg", "1.0")
    assert result is None
