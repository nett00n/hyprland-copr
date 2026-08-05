"""Tests for vendor_rust module."""

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
                generate("pkg", {}, Path(tmpdir), Path(tmpdir), Path(tmpdir) / "out.tar.gz")

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
                generate("pkg", {}, Path(tmpdir), Path(tmpdir), Path(tmpdir) / "out.tar.gz")

            assert "cargo check failed" in str(exc_info.value)

    @patch("lib.vendor_rust.subprocess.run")
    def test_no_cargo_toml_file(self, mock_run):
        """Test error when Cargo.toml doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "Cargo.toml" in str(exc_info.value)

    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_vendor_fails(self, mock_tar, mock_run):
        """Test error when cargo vendor fails."""
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
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "cargo vendor failed" in str(exc_info.value)

    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
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
            (src_dir / "Cargo.toml").write_text("[package]")

            with pytest.raises(VendorError) as exc_info:
                generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            assert "vendor/ directory" in str(exc_info.value)

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
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
            (src_dir / "Cargo.toml").write_text("[package]")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()
            cargo_dir = src_dir / ".cargo"
            cargo_dir.mkdir()

            generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify tarfile was created and files were added
            mock_tar.assert_called_once()
            assert mock_tf.add.call_count == 2  # vendor/ and .cargo/config.toml

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_generate_with_rust_subdir(self, mock_tar, mock_run, mock_rmtree):
        """Test generation with rust_subdir specified."""
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
            generate("pkg", pkg_meta, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify correct working directory was used
            calls = mock_run.call_args_list
            assert calls[1][1]["cwd"] == subdir

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
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
        (src_dir / "Cargo.toml").write_text("[package]")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()
        log_file = tmp_path / "vendor.log"

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz", log_file)

        # Verify log was written
        assert log_file.exists()
        content = log_file.read_text()
        assert "vendor output" in content
        assert "[exit: 0]" in content

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_config_created(self, mock_tar, mock_run, mock_rmtree, tmp_path):
        """Test that .cargo/config.toml is created with correct content."""
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

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

        # Verify .cargo/config.toml was created
        cargo_config = src_dir / ".cargo" / "config.toml"
        assert cargo_config.exists()
        content = cargo_config.read_text()
        assert "vendored-sources" in content
        assert "offline = true" in content

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
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
            (src_dir / "Cargo.toml").write_text("[package]")
            vendor_dir = src_dir / "vendor"
            vendor_dir.mkdir()
            (vendor_dir / "old_file.txt").write_text("should be removed")

            generate("pkg", {}, Path(tmpdir), src_dir, Path(tmpdir) / "out.tar.gz")

            # Verify rmtree was called to remove the old vendor directory
            mock_rmtree.assert_called_once()

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_vendor_command_args(self, mock_tar, mock_run, mock_rmtree, tmp_path):
        """Test that cargo vendor is called with correct arguments."""
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

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

        # Verify cargo vendor was called with vendor directory argument
        calls = mock_run.call_args_list
        cargo_call = calls[1]
        assert cargo_call[0][0][0] == "cargo"
        assert cargo_call[0][0][1] == "vendor"
        assert str(vendor_dir) in cargo_call[0][0]


class TestGitSourceCrateScan:
    """Test the TODO-0005 git-source-crate rejection."""

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    def test_git_source_crate_rejected(self, mock_run, mock_rmtree, tmp_path):
        version_result = MagicMock()
        version_result.returncode = 0
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""
        mock_run.side_effect = [version_result, vendor_result]

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")
        vendor_dir = src_dir / "vendor"
        vendor_dir.mkdir()
        crate_dir = vendor_dir / "some-git-crate"
        crate_dir.mkdir()
        (crate_dir / ".cargo-checksum.json").write_text('{"files": {}, "package": null}')

        with pytest.raises(VendorError, match="git-source crate"):
            generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_registry_crates_allowed(self, mock_tar, mock_run, mock_rmtree, tmp_path):
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
        crate_dir = vendor_dir / "some-crate-1.0.0"
        crate_dir.mkdir()
        (crate_dir / ".cargo-checksum.json").write_text(
            '{"files": {}, "package": "deadbeef"}'
        )

        # Should not raise.
        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")


class TestToolchainSkewIntegration:
    """Test the TODO-0007 fedora_version wiring."""

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    def test_skew_blocks_before_cargo_vendor(self, mock_run, mock_rmtree, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text(
            '[package]\nname = "foo"\nrust-version = "1.90"\n'
        )
        version_result = MagicMock()
        version_result.returncode = 0
        mock_run.return_value = version_result

        with patch(
            "lib.vendor_rust.rust_toolchain_skew", return_value="skew detected"
        ):
            with pytest.raises(VendorError, match="skew detected"):
                generate(
                    "pkg",
                    {},
                    tmp_path,
                    src_dir,
                    tmp_path / "out.tar.gz",
                    fedora_version="43",
                )
        # cargo --version only -- cargo vendor was never reached.
        assert mock_run.call_count == 1

    def test_no_fedora_version_skips_check(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")
        with patch("lib.vendor_rust.rust_toolchain_skew") as mock_skew:
            with patch("lib.vendor_rust.subprocess.run") as mock_run, patch(
                "lib.vendor_rust.shutil.rmtree"
            ), patch("lib.vendor_rust.tarfile.open"):
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


class TestCargoUpdate:
    """Test the cargo_update pre-vendor lockfile-bump hook."""

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_cargo_update_runs_before_vendor(
        self, mock_tar, mock_run, mock_rmtree, tmp_path
    ):
        version_result = MagicMock()
        version_result.returncode = 0
        update_result = MagicMock()
        update_result.returncode = 0
        update_result.stdout = ""
        update_result.stderr = ""
        vendor_result = MagicMock()
        vendor_result.returncode = 0
        vendor_result.stdout = ""
        vendor_result.stderr = ""
        mock_run.side_effect = [version_result, update_result, vendor_result]
        mock_tf = MagicMock()
        mock_tar.return_value.__enter__.return_value = mock_tf

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")
        (src_dir / "vendor").mkdir()

        pkg_meta = {"build": {"cargo_update": ["time@0.3.34"]}}
        generate("pkg", pkg_meta, tmp_path, src_dir, tmp_path / "out.tar.gz")

        calls = mock_run.call_args_list
        assert calls[1][0][0] == ["cargo", "update", "-p", "time@0.3.34"]
        assert calls[1][1]["cwd"] == src_dir
        # cargo update ran before cargo vendor.
        assert calls[2][0][0][:2] == ["cargo", "vendor"]

    @patch("lib.vendor_rust.subprocess.run")
    def test_cargo_update_failure_raises(self, mock_run, tmp_path):
        version_result = MagicMock()
        version_result.returncode = 0
        update_result = MagicMock()
        update_result.returncode = 1
        update_result.stderr = "no matching package named `bogus` found"
        mock_run.side_effect = [version_result, update_result]

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Cargo.toml").write_text("[package]")

        pkg_meta = {"build": {"cargo_update": ["bogus@1.0.0"]}}
        with pytest.raises(VendorError, match="cargo update -p bogus@1.0.0 failed"):
            generate("pkg", pkg_meta, tmp_path, src_dir, tmp_path / "out.tar.gz")

    @patch("lib.vendor_rust.shutil.rmtree")
    @patch("lib.vendor_rust.subprocess.run")
    @patch("lib.vendor_rust.tarfile.open")
    def test_no_cargo_update_field_skips_step(
        self, mock_tar, mock_run, mock_rmtree, tmp_path
    ):
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
        (src_dir / "vendor").mkdir()

        generate("pkg", {}, tmp_path, src_dir, tmp_path / "out.tar.gz")

        # Only cargo --version and cargo vendor -- no update call.
        assert mock_run.call_count == 2
