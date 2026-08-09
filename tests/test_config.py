"""Tests for lib.config module."""

import logging
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.config import env_flag, get_packager, setup_logging


class TestEnvFlag:
    """Test env_flag function."""

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES"])
    def test_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("FORCE_REBUILD", value)
        assert env_flag("FORCE_REBUILD") is True

    @pytest.mark.parametrize("value", ["", "0", "false", "FALSE", "no", "junk"])
    def test_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("FORCE_REBUILD", value)
        assert env_flag("FORCE_REBUILD") is False

    def test_unset_is_false(self, monkeypatch):
        monkeypatch.delenv("FORCE_REBUILD", raising=False)
        assert env_flag("FORCE_REBUILD") is False


class TestGetPackager:
    """Test get_packager function."""

    def test_returns_packager_env_var(self, monkeypatch):
        """Should return PACKAGER env var if set."""
        monkeypatch.setenv("PACKAGER", "John Doe <john@example.com>")
        result = get_packager()
        assert result == "John Doe <john@example.com>"

    def test_uses_packager_name_and_email_env_vars(self, monkeypatch):
        """Should use PACKAGER_NAME and PACKAGER_EMAIL if set."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.setenv("PACKAGER_NAME", "Jane")
        monkeypatch.setenv("PACKAGER_EMAIL", "jane@example.com")
        result = get_packager()
        assert result == "Jane <jane@example.com>"

    def test_loads_packager_from_env_file(self, tmp_path, monkeypatch):
        """Should load PACKAGER from .env file."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text('PACKAGER="Bob Smith <bob@example.com>"\n')
        monkeypatch.chdir(tmp_path)

        result = get_packager()
        assert result == "Bob Smith <bob@example.com>"

    def test_loads_packager_name_and_email_from_env_file(self, tmp_path, monkeypatch):
        """Should load PACKAGER_NAME and PACKAGER_EMAIL from .env file."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text(
            'PACKAGER_NAME="Alice"\nPACKAGER_EMAIL="alice@example.com"\n'
        )
        monkeypatch.chdir(tmp_path)

        result = get_packager()
        assert result == "Alice <alice@example.com>"

    def test_strips_quotes_from_env_file(self, tmp_path, monkeypatch):
        """Should strip single and double quotes from .env values."""
        monkeypatch.delenv("PACKAGER", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("PACKAGER='Charlie <charlie@example.com>'\n")
        monkeypatch.chdir(tmp_path)

        result = get_packager()
        assert result == "Charlie <charlie@example.com>"

    def test_env_var_priority_over_env_file(self, tmp_path, monkeypatch):
        """Should prefer PACKAGER env var over .env file."""
        monkeypatch.setenv("PACKAGER", "Grace <grace@example.com>")

        env_file = tmp_path / ".env"
        env_file.write_text('PACKAGER="Hank <hank@example.com>"\n')
        monkeypatch.chdir(tmp_path)

        result = get_packager()
        assert result == "Grace <grace@example.com>"

    def test_env_file_priority_over_git(self, tmp_path, monkeypatch):
        """Should prefer .env file over git config."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text('PACKAGER="Iris <iris@example.com>"\n')
        monkeypatch.chdir(tmp_path)

        with patch("subprocess.check_output") as mock_git:
            mock_git.side_effect = ["Jack\n", "jack@example.com\n"]
            result = get_packager()
            assert result == "Iris <iris@example.com>"


class TestSetupLogging:
    """Test setup_logging function."""

    def test_sets_log_level_from_env_var(self, monkeypatch):
        """Should set logging level from LOG_LEVEL env var."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        # Reset logging to allow basicConfig to work
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        setup_logging()

        assert logging.root.level == logging.DEBUG

    def test_defaults_to_info_level(self, monkeypatch):
        """Should default to INFO level if LOG_LEVEL not set."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        # Reset logging
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        setup_logging()

        assert logging.root.level == logging.INFO

    def test_supports_all_log_levels(self, monkeypatch):
        """Should support all standard log levels."""
        for level_name, level_int in [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]:
            monkeypatch.setenv("LOG_LEVEL", level_name)
            # Reset logging
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            setup_logging()
            assert logging.root.level == level_int

    def test_case_insensitive_log_level(self, monkeypatch):
        """Should handle lowercase log level."""
        monkeypatch.setenv("LOG_LEVEL", "warning")
        # Reset logging
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        setup_logging()
        assert logging.root.level == logging.WARNING

    def test_configures_format(self, monkeypatch):
        """Should configure format with level and message."""
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        # Reset logging
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        setup_logging()

        # The format should include "%(levelname)s: %(message)s"
        # We can verify by checking handlers
        logger = logging.getLogger()
        handler = logger.handlers[-1] if logger.handlers else None
        if handler and handler.formatter:
            assert "levelname" in handler.formatter._fmt


class TestGetPackagerGitFallback:
    """Test get_packager git fallback paths."""

    def test_skips_blank_and_comment_lines_in_env_file(self, tmp_path, monkeypatch):
        """Should skip blank lines and comments in .env file."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n"
            "\n"
            "PACKAGER=\"Test User <test@example.com>\"\n"
            "# Another comment\n"
        )
        monkeypatch.chdir(tmp_path)

        result = get_packager()
        assert result == "Test User <test@example.com>"

    def test_falls_back_to_git_config_success(self, tmp_path, monkeypatch):
        """Should use git config when no env vars or .env file."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)
        monkeypatch.chdir(tmp_path)

        with patch("subprocess.check_output") as mock_git:
            mock_git.side_effect = ["Git User\n", "git@example.com\n"]
            result = get_packager()

        assert result == "Git User <git@example.com>"

    def test_returns_default_when_git_returns_empty_strings(self, tmp_path, monkeypatch):
        """Should return default when git returns empty strings."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)
        monkeypatch.chdir(tmp_path)

        with patch("subprocess.check_output") as mock_git:
            mock_git.side_effect = ["\n", "\n"]
            result = get_packager()

        assert result == "Packager <packager@example.com>"

    def test_returns_default_when_git_not_found(self, tmp_path, monkeypatch):
        """Should return default when git command not found."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)
        monkeypatch.chdir(tmp_path)

        with patch("subprocess.check_output") as mock_git:
            mock_git.side_effect = FileNotFoundError()
            result = get_packager()

        assert result == "Packager <packager@example.com>"

    def test_returns_default_when_git_not_configured(self, tmp_path, monkeypatch):
        """Should return default when git config not set."""
        monkeypatch.delenv("PACKAGER", raising=False)
        monkeypatch.delenv("PACKAGER_NAME", raising=False)
        monkeypatch.delenv("PACKAGER_EMAIL", raising=False)
        monkeypatch.chdir(tmp_path)

        with patch("subprocess.check_output") as mock_git:
            mock_git.side_effect = subprocess.CalledProcessError(1, "git")
            result = get_packager()

        assert result == "Packager <packager@example.com>"
