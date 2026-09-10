"""Tests for lib.subprocess_utils module."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.subprocess_utils import _cmd_timeout, run_cmd, run_git


class TestRunCmd:
    """Test run_cmd function."""

    def test_successful_command(self):
        """Should return True for successful command."""
        ok, stdout, stderr = run_cmd(["true"])
        assert ok is True
        assert stderr == ""

    def test_failed_command(self):
        """Should return False for failed command."""
        ok, stdout, stderr = run_cmd(["false"])
        assert ok is False

    def test_command_with_output(self):
        """Should capture stdout from command."""
        ok, stdout, stderr = run_cmd(["echo", "hello"])
        assert ok is True
        assert "hello" in stdout

    def test_command_not_found(self):
        """Should handle command not found gracefully."""
        ok, stdout, stderr = run_cmd(["nonexistent-xyz-abc-command-123"])
        assert ok is False
        assert "command not found" in stderr

    def test_command_with_log_path(self, tmp_path):
        """Should write output to log file."""
        log_file = tmp_path / "test.log"
        ok, stdout, stderr = run_cmd(["echo", "test output"], log_path=log_file)

        assert ok is True
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "test output" in log_content
        assert "exit: 0" in log_content

    def test_log_path_creates_parent_dirs(self, tmp_path):
        """Should create parent directories for log file."""
        log_file = tmp_path / "nested" / "deep" / "test.log"
        run_cmd(["echo", "test"], log_path=log_file)

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_log_file_appends(self, tmp_path):
        """Should append to log file, not overwrite."""
        log_file = tmp_path / "test.log"

        run_cmd(["echo", "first"], log_path=log_file)
        run_cmd(["echo", "second"], log_path=log_file)

        log_content = log_file.read_text()
        assert "first" in log_content
        assert "second" in log_content

    def test_timeout_exceeded(self):
        """Should handle timeout gracefully."""
        ok, stdout, stderr = run_cmd(["sleep", "10"], timeout=1)
        assert ok is False
        assert "timed out" in stderr

    def test_command_with_stderr(self):
        """Should capture stderr."""
        # Use a command that writes to stderr
        ok, stdout, stderr = run_cmd(["sh", "-c", "echo error >&2"])
        assert "error" in stderr

    def test_return_values_are_strings(self):
        """Should return strings for stdout/stderr."""
        ok, stdout, stderr = run_cmd(["echo", "test"])
        assert isinstance(ok, bool)
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)

    def test_empty_stdout_stderr_with_failure(self):
        """Should handle empty output on failure."""
        ok, stdout, stderr = run_cmd(["false"])
        assert ok is False
        assert stdout == ""
        assert stderr == ""

    def test_cwd(self, tmp_path):
        """Should run the command in the given working directory."""
        (tmp_path / "marker.txt").write_text("hi")
        ok, stdout, stderr = run_cmd(["ls"], cwd=tmp_path)
        assert ok is True
        assert "marker.txt" in stdout


class TestCmdTimeout:
    """Test _cmd_timeout() -- CMD_TIMEOUT env var parsing."""

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("CMD_TIMEOUT", raising=False)
        assert _cmd_timeout() == 3600

    def test_default_when_empty(self, monkeypatch):
        monkeypatch.setenv("CMD_TIMEOUT", "")
        assert _cmd_timeout() == 3600

    def test_parses_valid_integer(self, monkeypatch):
        monkeypatch.setenv("CMD_TIMEOUT", "120")
        assert _cmd_timeout() == 120

    def test_falls_back_on_invalid_value(self, monkeypatch, capsys):
        monkeypatch.setenv("CMD_TIMEOUT", "30s")
        assert _cmd_timeout() == 3600
        assert "CMD_TIMEOUT" in capsys.readouterr().err

    def test_run_cmd_does_not_raise_on_invalid_cmd_timeout(self, monkeypatch):
        """A malformed CMD_TIMEOUT must not crash run_cmd() (previously raised ValueError)."""
        monkeypatch.setenv("CMD_TIMEOUT", "not-a-number")
        ok, stdout, stderr = run_cmd(["echo", "ok"])
        assert ok is True
        assert "ok" in stdout


class TestRunGit:
    """Test run_git function."""

    def test_git_version_command(self):
        """Should run git version command."""
        result = run_git("--version")
        assert result.returncode == 0
        assert "git version" in result.stdout

    def test_git_invalid_command(self):
        """Should return non-zero exit code for invalid git command."""
        result = run_git("nonexistent-subcommand")
        assert result.returncode != 0

    def test_git_captures_stdout(self):
        """Should capture stdout from git command."""
        result = run_git("--version")
        assert result.stdout != ""
        assert isinstance(result.stdout, str)

    def test_git_captures_stderr(self):
        """Should capture stderr."""
        result = run_git("nonexistent-subcommand")
        # stderr might contain error message (depends on git)
        assert isinstance(result.stderr, str)

    def test_git_with_cwd(self, tmp_path):
        """Should use working directory if provided."""
        # Initialize a git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        result = run_git("status", cwd=tmp_path)
        assert result.returncode == 0
        assert "On branch" in result.stdout or "working tree clean" in result.stdout

    def test_git_with_timeout(self):
        """Should respect timeout parameter."""
        # git --version completes quickly, so this should succeed
        result = run_git("--version", timeout=300)
        assert result.returncode == 0

    def test_git_returns_completed_process(self):
        """Should return CompletedProcess object."""
        import subprocess
        result = run_git("--version")
        assert isinstance(result, subprocess.CompletedProcess)
        assert hasattr(result, "returncode")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")

    def test_git_missing_binary_does_not_raise(self):
        """A missing git binary should be reported, not raised (returncode=127)."""
        with patch("lib.subprocess_utils.subprocess.run", side_effect=FileNotFoundError):
            result = run_git("status")
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 127
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_git_timeout_does_not_raise(self):
        """A timed-out git command should be reported, not raised (returncode=124)."""
        with patch(
            "lib.subprocess_utils.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git status", timeout=5),
        ):
            result = run_git("status", timeout=5)
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 124
        assert result.stdout == ""
        assert "timed out after 5s" in result.stderr
