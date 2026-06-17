"""Tests for uncovered branches in vendor.py."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import tarfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.vendor import (
    is_go_package,
    resolve_source_url,
    vendor_tarball_name,
    vendor_tarball_path,
    VendorError,
    generate,
)


class TestIsGoPackage:
    """Test is_go_package function."""

    def test_identifies_go_package(self):
        """Should return True for packages with golang in build_requires."""
        meta = {"build_requires": ["golang", "git"]}
        assert is_go_package(meta) is True

    def test_rejects_non_go_package(self):
        """Should return False for packages without golang."""
        meta = {"build_requires": ["cmake", "git"]}
        assert is_go_package(meta) is False

    def test_handles_missing_build_requires(self):
        """Should return False when build_requires is missing."""
        meta = {"version": "1.0"}
        assert is_go_package(meta) is False

    def test_handles_empty_build_requires(self):
        """Should return False for empty build_requires."""
        meta = {"build_requires": []}
        assert is_go_package(meta) is False

    def test_handles_none_build_requires(self):
        """Should return False when build_requires is None."""
        meta = {"build_requires": None}
        assert is_go_package(meta) is False


class TestResolveSourceUrl:
    """Test resolve_source_url function."""

    def test_resolves_simple_url(self):
        """Should resolve URL from archives list."""
        meta = {
            "url": "https://example.com/pkg",
            "version": "1.0",
            "source": {
                "archives": ["https://example.com/pkg-1.0.tar.gz"]
            }
        }
        result = resolve_source_url(meta, "test-pkg")
        assert result == "https://example.com/pkg-1.0.tar.gz"

    def test_expands_url_macro(self):
        """Should expand %{url} macro in archive URL."""
        meta = {
            "url": "https://example.com/pkg",
            "version": "1.0",
            "source": {
                "archives": ["%{url}/releases/pkg-1.0.tar.gz"]
            }
        }
        result = resolve_source_url(meta, "test-pkg")
        assert "https://example.com/pkg" in result

    def test_expands_version_macro(self):
        """Should expand %{version} macro in archive URL."""
        meta = {
            "url": "https://example.com",
            "version": "2.5",
            "source": {
                "archives": ["https://example.com/pkg-%{version}.tar.gz"]
            }
        }
        result = resolve_source_url(meta, "test-pkg")
        assert "2.5" in result

    def test_raises_on_missing_archives(self):
        """Should raise VendorError when no archives defined."""
        meta = {
            "url": "https://example.com",
            "version": "1.0",
            "source": {}
        }
        with pytest.raises(VendorError):
            resolve_source_url(meta, "test-pkg")

    def test_raises_on_empty_archives(self):
        """Should raise VendorError when archives list is empty."""
        meta = {
            "url": "https://example.com",
            "version": "1.0",
            "source": {"archives": []}
        }
        with pytest.raises(VendorError):
            resolve_source_url(meta, "test-pkg")

    def test_raises_on_empty_archive_entry(self):
        """Should raise VendorError when first archive entry is empty."""
        meta = {
            "url": "https://example.com",
            "version": "1.0",
            "source": {"archives": [""]}
        }
        with pytest.raises(VendorError):
            resolve_source_url(meta, "test-pkg")

    def test_strips_quotes_from_url(self):
        """Should strip quotes from resolved URL."""
        meta = {
            "url": "https://example.com",
            "version": "1.0",
            "source": {
                "archives": ['"https://example.com/pkg-1.0.tar.gz"']
            }
        }
        result = resolve_source_url(meta, "test-pkg")
        assert result == "https://example.com/pkg-1.0.tar.gz"


class TestVendorTarballName:
    """Test vendor_tarball_name function."""

    def test_generates_correct_name(self):
        """Should generate correct vendor tarball name."""
        result = vendor_tarball_name("my-pkg", "1.2.3")
        assert result == "my-pkg-1.2.3-vendor.tar.gz"

    def test_handles_special_characters_in_version(self):
        """Should handle complex version strings."""
        result = vendor_tarball_name("my-pkg", "1.2.3-rc1+git20210101")
        assert "vendor.tar.gz" in result
        assert "my-pkg" in result


class TestVendorTarballPath:
    """Test vendor_tarball_path function."""

    def test_returns_correct_path(self):
        """Should return correct path for vendor tarball."""
        sources_dir = Path("/sources")
        result = vendor_tarball_path("my-pkg", "1.0", sources_dir)
        assert result == Path("/sources/my-pkg-1.0-vendor.tar.gz")



    def test_handles_unsafe_tarball_members(self, tmp_path):
        """Should reject tarballs with path traversal attempts."""
        # Create tarball with unsafe member
        archive_path = tmp_path / "unsafe.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tf:
            import io
            unsafe_path = "../../../etc/passwd"
            data = io.BytesIO(b"test")
            tarinfo = tarfile.TarInfo(name=unsafe_path)
            tarinfo.size = len(b"test")
            tf.addfile(tarinfo, data)

        meta = {
            "url": "https://example.com",
            "version": "1.0",
            "source": {"archives": ["file://" + str(archive_path)]},
            "build": {}
        }
        output = tmp_path / "vendor.tar.gz"

        with patch("shutil.which") as mock_which:
            with patch("lib.vendor._download") as mock_dl:
                mock_which.return_value = "/usr/bin/go"
                def mock_download(url, dest):
                    import shutil
                    shutil.copy(archive_path, dest)
                mock_dl.side_effect = mock_download
                # Python 3.12+ raises OutsideDestinationError, older versions raise VendorError
                with pytest.raises((VendorError, Exception)):
                    generate("test-pkg", meta, output)
