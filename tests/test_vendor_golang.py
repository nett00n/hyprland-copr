"""Tests for vendor_golang module."""

import subprocess
import sys
import tempfile
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.vendor_golang import VendorError, generate, _log_fn


class TestLogFn:
    """Tests for _log_fn helper."""

    def test_log_fn_without_file(self, capsys):
        """Test logging to stdout only."""
        log = _log_fn(None)
        log("test message")

        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_log_fn_with_file(self, tmp_path):
        """Test logging to both stdout and file."""
        log_file = tmp_path / "test.log"
        log = _log_fn(log_file)
        log("test message")

        assert log_file.exists()
        assert "test message" in log_file.read_text()

    def test_log_fn_multiple_messages(self, tmp_path):
        """Test multiple log messages."""
        log_file = tmp_path / "test.log"
        log = _log_fn(log_file)
        log("message 1")
        log("message 2")
        log("message 3")

        content = log_file.read_text()
        assert "message 1" in content
        assert "message 2" in content
        assert "message 3" in content


class TestGenerate:
    """Tests for generate function."""

    @patch("lib.vendor_golang.subprocess.run")
    def test_go_not_in_path(self, mock_run):
        """Test error when go is not available."""
        mock_run.side_effect = FileNotFoundError()

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), Path(tmpdir), Path(tmpdir))

            assert "go" in str(exc_info.value).lower()
            assert "not found" in str(exc_info.value).lower()

    @patch("lib.vendor_golang.subprocess.run")
    def test_go_version_fails(self, mock_run):
        """Test error when go version check fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "go not installed"
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), Path(tmpdir), Path(tmpdir))

            assert "go check failed" in str(exc_info.value)

    @patch("lib.vendor_golang.subprocess.run")
    def test_no_go_mod_file(self, mock_run):
        """Test error when go.mod doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "go.mod" in str(exc_info.value)

    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_go_mod_vendor_fails(self, mock_tar, mock_run):
        """Test error when go mod vendor fails."""
        # First call: go version (success)
        version_result = MagicMock()
        version_result.returncode = 0
        # Second call: go mod vendor (failure)
        vendor_result = MagicMock()
        vendor_result.returncode = 1
        vendor_result.stderr = "vendor failed"

        mock_run.side_effect = [version_result, vendor_result]

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "go.mod").write_text("module test")

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "go mod vendor failed" in str(exc_info.value)

    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_vendor_dir_not_created(self, mock_tar, mock_run):
        """Test error when vendor directory is not created."""
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0

        mock_run.side_effect = [version_result, vendor_result]

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "go.mod").write_text("module test")

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "vendor/ directory" in str(exc_info.value)

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_generate_success(self, mock_tar, mock_run, mock_rmtree):
        """Test successful vendor generation."""
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "go.mod").write_text("module test")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()

            generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify tarfile was created
            mock_tar.assert_called_once()
            mock_tf.add.assert_called_once_with(vendor_dir, arcname="vendor")

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_generate_with_go_subdir(self, mock_tar, mock_run, mock_rmtree):
        """Test generation with go_subdir specified."""
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            subdir = src_dir / "subdir"
            subdir.mkdir(parents=True)
            (subdir / "go.mod").write_text("module test")
            vendor_dir = subdir / "vendor"
            vendor_dir.mkdir()

            pkg_meta = {"build": {"go_subdir": "subdir"}}
            generate("pkg", pkg_meta, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify correct working directory was used
            calls = mock_run.call_args_list
            assert calls[1][1]["cwd"] == subdir

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_generate_with_log_file(self, mock_tar, mock_run, mock_rmtree, tmp_path):
        """Test that output is logged to file."""
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = "vendor output"
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module test")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()
        log_file = tmp_path / "vendor.log"

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz", log_file)

        # Verify log was written
        assert log_file.exists()
        content = log_file.read_text()
        assert "vendor output" in content
        assert "[exit: 0]" in content

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_existing_vendor_dir_removed(self, mock_tar, mock_run, mock_rmtree):
        """Test that existing vendor directory is removed."""
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "go.mod").write_text("module test")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()
            (vendor_dir / "old_file.txt").write_text("should be removed")

            generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify rmtree was called to remove the old vendor directory
            mock_rmtree.assert_called_once()


class TestToolchainSkewIntegration:
    """Test the TODO-0007 fedora_version wiring."""

    @patch("lib.vendor_golang.subprocess.run")
    def test_skew_blocks_before_go_mod_vendor(self, mock_run, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module foo\n\ntoolchain go1.99.0\n")
        version_result = MagicMock()
        version_result.returncode = 0
        mock_run.return_value = version_result

        with patch("lib.vendor_golang.go_toolchain_skew", return_value="skew detected"):
            with pytest.raises(VendorError, match="skew detected"):
                generate(
                    "pkg",
                    {},
                    tmp_path,
                    src_dir,
                    tmp_path / "out.tar.gz",
                    fedora_version="43",
                )
        # go version only -- go mod vendor was never reached.
        assert mock_run.call_count == 1

    def test_no_fedora_version_skips_check(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module foo")
        with patch("lib.vendor_golang.go_toolchain_skew") as mock_skew:
            with patch("lib.vendor_golang.subprocess.run") as mock_run, patch(
                "lib.vendor_golang.tarfile.open"
            ), patch("lib.vendor_golang.shutil.rmtree"):
                version_result = MagicMock()
                version_result.returncode = 0
                vendor_result = MagicMock()
                vendor_result.returncode = 0
                vendor_result.stdout = ""
                vendor_result.stderr = ""
                mock_run.side_effect = [version_result, vendor_result]
                (src_dir / "vendor").mkdir()
                generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")
        mock_skew.assert_not_called()


class TestTimeout:
    """docs/bugs.md BUG-0024: `go mod vendor` ran with no timeout at all, so a
    hung invocation blocked update-daily indefinitely. It now goes through
    lib.subprocess_utils.run_cmd, which reads CMD_TIMEOUT (default 3600s) and
    turns a timeout into an (ok=False, ...) result instead of letting
    subprocess.TimeoutExpired propagate uncaught; generate() wraps that into a
    VendorError.
    """

    @patch("lib.vendor_golang.subprocess.run")
    def test_timeout_raises_vendor_error(self, mock_run, tmp_path):
        version_result = MagicMock()
        version_result.returncode = 0
        mock_run.side_effect = [
            version_result,
            subprocess.TimeoutExpired(cmd=["go", "mod", "vendor"], timeout=3600),
        ]

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module test")

        with pytest.raises(VendorError, match="go mod vendor failed.*timed out after 3600s"):
            generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_default_timeout(
        self, mock_tar, mock_run, mock_rmtree, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("CMD_TIMEOUT", raising=False)
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""
        mock_run.side_effect = [version_result, vendor_result]

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module test")
        (src_dir / "vendor").mkdir()

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

        assert mock_run.call_args_list[1][1]["timeout"] == 3600

    @patch("lib.vendor_golang.shutil.rmtree")
    @patch("lib.vendor_golang.subprocess.run")
    @patch("lib.vendor_golang.tarfile.open")
    def test_respects_cmd_timeout_env(
        self, mock_tar, mock_run, mock_rmtree, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CMD_TIMEOUT", "120")
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""
        mock_run.side_effect = [version_result, vendor_result]

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "go.mod").write_text("module test")
        (src_dir / "vendor").mkdir()

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

        assert mock_run.call_args_list[1][1]["timeout"] == 120
