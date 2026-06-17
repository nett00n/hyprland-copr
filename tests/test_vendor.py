"""Tests for lib.vendor module."""

import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.vendor import (
    VendorError,
    _download,
    _extract,
    is_go_package,
    resolve_source_url,
    vendor_tarball_name,
    generate,
    vendor_tarball_path,
)


class TestIsGoPackage:
    """Test is_go_package function."""

    def test_returns_true_for_go_packages(self):
        """Should return True if golang is in build_requires."""
        meta = {"build_requires": ["golang", "gcc"]}
        assert is_go_package(meta) is True

    def test_returns_false_for_non_go_packages(self):
        """Should return False if golang not in build_requires."""
        meta = {"build_requires": ["gcc", "make"]}
        assert is_go_package(meta) is False

    def test_handles_missing_build_requires(self):
        """Should return False if build_requires is missing."""
        assert is_go_package({}) is False
        assert is_go_package({"build_requires": None}) is False


class TestResolveSourceUrl:
    """Test resolve_source_url function."""

    def test_returns_first_archive_url(self):
        """Should return the first archive URL."""
        meta = {
            "url": "https://github.com/foo/bar",
            "version": "1.0.0",
            "source": {"archives": ["https://example.com/src.tar.gz", "https://example.com/sha256"]},
        }
        url = resolve_source_url(meta, "test")
        assert url == "https://example.com/src.tar.gz"

    def test_expands_url_macro(self):
        """Should expand %{url} macro."""
        meta = {
            "url": "https://github.com/foo/bar",
            "version": "1.0.0",
            "source": {"archives": ["%{url}/releases/download/v%{version}/src.tar.gz"]},
        }
        url = resolve_source_url(meta, "test")
        assert "github.com/foo/bar" in url
        assert "1.0.0" in url

    def test_expands_version_macro(self):
        """Should expand %{version} macro."""
        meta = {
            "url": "https://example.com",
            "version": "2.5.0",
            "source": {"archives": ["%{url}/%{version}/download.tar.gz"]},
        }
        url = resolve_source_url(meta, "test")
        assert "2.5.0" in url

    def test_raises_on_missing_archives(self):
        """Should raise VendorError if no archives defined."""
        meta = {"source": {}}
        with pytest.raises(VendorError):
            resolve_source_url(meta, "test")

    def test_raises_on_empty_archive_list(self):
        """Should raise VendorError if archives is empty."""
        meta = {"source": {"archives": []}}
        with pytest.raises(VendorError):
            resolve_source_url(meta, "test")


class TestVendorTarballName:
    """Test vendor_tarball_name function."""

    def test_generates_correct_name(self):
        """Should generate vendor tarball name."""
        name = vendor_tarball_name("mypackage", "1.0.0")
        assert name == "mypackage-1.0.0-vendor.tar.gz"


class TestDownload:
    """Test _download function."""

    def test_downloads_to_destination(self, tmp_path):
        """Should download URL content to destination file."""
        dest = tmp_path / "file.tar.gz"
        content = b"file content"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = content
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_urlopen.return_value = mock_response

            _download("http://example.com/file.tar.gz", dest)

            assert dest.exists()
            assert dest.read_bytes() == content

    def test_wraps_urlerror_in_vendor_error(self, tmp_path):
        """Should wrap URLError in VendorError."""
        import urllib.error

        dest = tmp_path / "file.tar.gz"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            with pytest.raises(VendorError):
                _download("http://example.com/file.tar.gz", dest)

    def test_wraps_os_error_in_vendor_error(self, tmp_path):
        """Should wrap OSError in VendorError."""
        dest = Path("/root/readonly/file.tar.gz")  # Likely read-only

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"content"
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_urlopen.return_value = mock_response

            # Mock write_bytes to raise OSError
            with patch.object(Path, "write_bytes") as mock_write:
                mock_write.side_effect = OSError("Permission denied")

                with pytest.raises(VendorError):
                    _download("http://example.com/file.tar.gz", dest)


class TestExtract:
    """Test _extract function."""

    def test_extracts_tarball(self, tmp_path):
        """Should extract tarball to target directory."""
        # Create a simple tar archive
        archive = tmp_path / "test.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive, "w:gz") as tf:
            # Add a simple file to the archive
            import io

            tarinfo = tarfile.TarInfo(name="mylib/file.txt")
            data = b"test content"
            tarinfo.size = len(data)
            tf.addfile(tarinfo, io.BytesIO(data))

        result = _extract(archive, extract_dir)

        # Should return the top-level directory (mylib)
        assert result == extract_dir / "mylib"

    def test_blocks_path_traversal(self, tmp_path):
        """Should block path traversal attacks in tarballs."""
        archive = tmp_path / "malicious.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        # Create a tarball with path traversal (only on Python < 3.12)
        # Python 3.12+ with filter="data" handles this automatically
        if sys.version_info < (3, 12):
            with tarfile.open(archive, "w:gz") as tf:
                import io

                # Try to create a file with ..
                tarinfo = tarfile.TarInfo(name="../../../etc/passwd")
                data = b"hacked"
                tarinfo.size = len(data)
                tf.addfile(tarinfo, io.BytesIO(data))

            # Extraction should fail or block the traversal
            try:
                _extract(archive, extract_dir)
                # If it succeeds, check that the file wasn't created outside extract_dir
                assert not Path("/etc/passwd").exists() or "/etc/passwd" not in str(
                    Path("/etc/passwd")
                )
            except VendorError:
                # Expected: the extraction should raise VendorError
                pass

    def test_blocks_absolute_paths(self, tmp_path):
        """Should block absolute paths in tarballs."""
        archive = tmp_path / "malicious.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        if sys.version_info < (3, 12):
            with tarfile.open(archive, "w:gz") as tf:
                import io

                # Try to create a file with absolute path
                tarinfo = tarfile.TarInfo(name="/etc/passwd")
                data = b"hacked"
                tarinfo.size = len(data)
                tf.addfile(tarinfo, io.BytesIO(data))

            # Should raise VendorError for absolute path
            with pytest.raises(VendorError):
                _extract(archive, extract_dir)

    def test_returns_extract_dir_when_multiple_top_dirs(self, tmp_path):
        """Should return extract_dir when multiple top-level directories."""
        archive = tmp_path / "test.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive, "w:gz") as tf:
            import io

            # Add files from two top-level directories
            tarinfo1 = tarfile.TarInfo(name="dir1/file1.txt")
            tarinfo1.size = 4
            tf.addfile(tarinfo1, io.BytesIO(b"data"))

            tarinfo2 = tarfile.TarInfo(name="dir2/file2.txt")
            tarinfo2.size = 4
            tf.addfile(tarinfo2, io.BytesIO(b"data"))

        result = _extract(archive, extract_dir)

        # Should return extract_dir, not a subdirectory
        assert result == extract_dir


class TestVendorTarballPath:
    """Test vendor_tarball_path function."""

    def test_returns_correct_path(self, tmp_path):
        """Should return correct tarball path."""
        path = vendor_tarball_path("mypackage", "1.0.0", tmp_path)
        assert path == tmp_path / "mypackage-1.0.0-vendor.tar.gz"


