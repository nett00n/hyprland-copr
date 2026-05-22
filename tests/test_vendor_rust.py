"""Tests for vendor_rust module."""

import subprocess
import sys
import tempfile
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.vendor_rust import VendorError, generate, _log_fn


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

    @patch("lib.vendor_rust.shutil.which")
    def test_cargo_not_in_path(self, mock_which):
        """Test error when cargo is not available."""
        mock_which.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir) / "out.tar.gz", submodule_path=Path(tmpdir))

            assert "cargo" in str(exc_info.value).lower()
            assert "not found" in str(exc_info.value).lower()

    @patch("lib.vendor_rust.shutil.which")
    @patch("lib.vendor_rust.subprocess.run")
    def test_cargo_version_fails(self, mock_run, mock_which):
        """Test error when cargo version check fails."""
        mock_which.return_value = "/usr/bin/cargo"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "cargo not installed"
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir) / "out.tar.gz", submodule_path=Path(tmpdir))

            assert "cargo check failed" in str(exc_info.value)

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.subprocess.run")
    def test_no_cargo_toml_file(self, mock_run, mock_resolve):
        """Test error when Cargo.toml doesn't exist."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir) / "out.tar.gz", submodule_path=src_dir)

            assert "Cargo.toml" in str(exc_info.value)

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_vendor_fails(self, mock_tar, mock_run, mock_resolve):
        """Test error when cargo vendor fails."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
        # First call: cargo --version (success)
        version_result = MagicMock()
        version_result.returncode = 0
        # Second call: cargo vendor (failure)
        vendor_result = MagicMock()
        vendor_result.returncode = 1
        vendor_result.stderr = "vendor failed"

        mock_run.side_effect = [version_result, vendor_result]

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "Cargo.toml").write_text("[package]")

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir) / "out.tar.gz", submodule_path=src_dir)

            assert "cargo vendor failed" in str(exc_info.value)

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_vendor_dir_not_created(self, mock_tar, mock_run, mock_resolve):
        """Test error when vendor directory is not created."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0

        mock_run.side_effect = [version_result, vendor_result]

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "Cargo.toml").write_text("[package]")

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir) / "out.tar.gz", submodule_path=src_dir)

            assert "vendor/ directory" in str(exc_info.value)

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_generate_success(self, mock_tar, mock_run, mock_rmtree, mock_resolve):
        """Test successful vendor generation."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
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
            (src_dir / "Cargo.toml").write_text("[package]")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()
            cargo_dir = src_dir / ".cargo"
            cargo_dir.mkdir()

            generate("pkg", {}, Path(tmpdir) / "out.tar.gz", src_dir, False, None)

            # Verify tarfile was created and files were added
            mock_tar.assert_called_once()
            assert mock_tf.add.call_count == 2  # vendor/ and .cargo/config.toml

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_generate_with_rust_subdir(self, mock_tar, mock_run, mock_rmtree, mock_resolve):
        """Test generation with rust_subdir specified."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
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
            (subdir / "Cargo.toml").write_text("[package]")
            vendor_dir = subdir / "vendor"
            vendor_dir.mkdir()

            pkg_meta = {"build": {"rust_subdir": "subdir"}}
            generate("pkg", pkg_meta, Path(tmpdir) / "out.tar.gz", src_dir, False, None)

            # Verify correct working directory was used
            calls = mock_run.call_args_list
            assert calls[1][1]["cwd"] == subdir

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_generate_with_log_file(self, mock_tar, mock_run, mock_rmtree, mock_resolve, tmp_path):
        """Test that output is logged to file."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
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
        (src_dir / "Cargo.toml").write_text("[package]")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()
        log_file = tmp_path / "vendor.log"

        generate("pkg", {}, tmp_path / "out.tar.gz", log_path=log_file, submodule_path=src_dir)

        # Verify log was written
        assert log_file.exists()
        content = log_file.read_text()
        assert "vendor output" in content
        assert "[exit: 0]" in content

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_config_created(self, mock_tar, mock_run, mock_rmtree, mock_resolve, tmp_path):
        """Test that .cargo/config.toml is created with correct content."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()

        generate("pkg", {}, tmp_path / "out.tar.gz", submodule_path=src_dir)

        # Verify .cargo/config.toml was created
        cargo_config = src_dir / ".cargo" / "config.toml"
        assert cargo_config.exists()
        content = cargo_config.read_text()
        assert "vendored-sources" in content
        assert "offline = true" in content

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_existing_vendor_dir_removed(self, mock_tar, mock_run, mock_rmtree, mock_resolve):
        """Test that existing vendor directory is removed."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
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
            (src_dir / "Cargo.toml").write_text("[package]")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()
            (vendor_dir / "old_file.txt").write_text("should be removed")

            generate("pkg", {}, Path(tmpdir) / "out.tar.gz", None, False, src_dir)

            # Verify rmtree was called to remove the old vendor directory
            mock_rmtree.assert_called_once()

    @patch("lib.vendor_rust.resolve_source_url")
    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_vendor_command_args(self, mock_tar, mock_run, mock_rmtree, mock_resolve, tmp_path):
        """Test that cargo vendor is called with correct arguments."""
        mock_resolve.return_value = "https://example.com/test.tar.gz"
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""

        mock_run.side_effect = [version_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()

        generate("pkg", {}, tmp_path / "out.tar.gz", submodule_path=src_dir)

        # Verify cargo vendor was called with vendor directory argument
        calls = mock_run.call_args_list
        cargo_call = calls[1]
        assert cargo_call[0][0][0] == "cargo"
        assert cargo_call[0][0][1] == "vendor"
        assert str(vendor_dir) in cargo_call[0][0]
