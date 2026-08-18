"""Tests for lib.vendor module."""

import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib import paths
from lib.source_lock import save_lock, sha256_file
from lib.vendor import (
    VendorError,
    _download,
    _extract,
    is_go_package,
    needs_vendoring,
    resolve_source_url,
    vendor_tarball_name,
    generate,
    vendor_tarball_path,
    verify_download,
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


class TestNeedsVendoring:
    """Test needs_vendoring function: truth table over is_go_package/is_rust_package."""

    def test_go_package_needs_vendoring(self):
        assert needs_vendoring({"build_requires": ["golang"]}) is True

    def test_rust_package_needs_vendoring(self):
        assert needs_vendoring({"build_requires": ["cargo"]}) is True

    def test_both_go_and_rust_needs_vendoring(self):
        assert needs_vendoring({"build_requires": ["golang", "cargo"]}) is True

    def test_neither_does_not_need_vendoring(self):
        assert needs_vendoring({"build_requires": ["gcc", "make"]}) is False

    def test_missing_build_requires_does_not_need_vendoring(self):
        assert needs_vendoring({}) is False

    def test_empty_build_requires_does_not_need_vendoring(self):
        assert needs_vendoring({"build_requires": []}) is False


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
        """Should refuse to extract a member that escapes extract_dir."""
        archive = tmp_path / "malicious.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive, "w:gz") as tf:
            import io

            tarinfo = tarfile.TarInfo(name="../../../etc/passwd")
            data = b"hacked"
            tarinfo.size = len(data)
            tf.addfile(tarinfo, io.BytesIO(data))

        # tarfile's filter="data" (Python 3.12+, the only version this
        # project runs on) raises OutsideDestinationError for this member.
        with pytest.raises(tarfile.OutsideDestinationError):
            _extract(archive, extract_dir)

    def test_contains_absolute_paths_within_extract_dir(self, tmp_path):
        """Should extract an absolute-path member inside extract_dir, not at the real path."""
        archive = tmp_path / "malicious.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive, "w:gz") as tf:
            import io

            tarinfo = tarfile.TarInfo(name="/etc/passwd")
            data = b"hacked"
            tarinfo.size = len(data)
            tf.addfile(tarinfo, io.BytesIO(data))

        # tarfile's filter="data" strips the leading "/" and contains the
        # member under extract_dir instead of raising.
        _extract(archive, extract_dir)
        assert (extract_dir / "etc" / "passwd").read_bytes() == b"hacked"

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


class TestVerifyDownload:
    """The Go/Rust vendor path downloads its own tarball (this module's
    _download) rather than going through spectool, so stage-srpm.py's
    verify-before-rpmbuild check never sees it -- verify_download() is the
    equivalent fail-closed check for that path (BUG-0025).
    """

    META = {
        "url": "https://example.com/pkg",
        "version": "1.0",
        "source": {
            "archives": ["%{url}/archive/v%{version}.tar.gz#/pkg-1.0.tar.gz"]
        },
    }
    URL = "https://example.com/pkg/archive/v1.0.tar.gz#/pkg-1.0.tar.gz"

    @pytest.fixture(autouse=True)
    def lock_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "SOURCES_LOCK", tmp_path / "sources.lock.yaml")

    def test_passes_when_hash_matches(self, tmp_path):
        archive = tmp_path / "downloaded.tar.gz"
        archive.write_bytes(b"tarball contents")
        save_lock(
            {"pkg": {"pkg-1.0.tar.gz": {"sha256": sha256_file(archive), "url": "x"}}}
        )
        verify_download("pkg", self.META, self.URL, archive)  # must not raise

    def test_raises_on_unrecorded_source(self, tmp_path):
        archive = tmp_path / "downloaded.tar.gz"
        archive.write_bytes(b"tarball contents")
        with pytest.raises(VendorError, match="no entry in sources.lock.yaml"):
            verify_download("pkg", self.META, self.URL, archive)

    def test_raises_on_hash_mismatch(self, tmp_path):
        archive = tmp_path / "downloaded.tar.gz"
        archive.write_bytes(b"tampered contents")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})
        with pytest.raises(VendorError, match="sha256 mismatch"):
            verify_download("pkg", self.META, self.URL, archive)

    def test_raises_when_url_not_in_remote_sources(self, tmp_path):
        """A URL that doesn't match this package's own source.archives at all
        (e.g. a bug upstream in how the caller resolved it) has nothing in
        the lock to check it against -- fail closed rather than skip silently.
        """
        archive = tmp_path / "downloaded.tar.gz"
        archive.write_bytes(b"tarball contents")
        with pytest.raises(VendorError, match="not a recognized remote source"):
            verify_download("pkg", self.META, "https://evil.example.com/x.tar.gz", archive)


class TestGenerateDispatch:
    """Dispatcher coverage: download -> verify_download -> extract -> language
    module, tmpdir removed afterwards, for both languages -- plus the
    both-languages-listed guard.
    """

    def _meta(self, build_requires):
        return {
            "build_requires": build_requires,
            "url": "https://example.com/pkg",
            "version": "1.0.0",
            "source": {"archives": ["https://example.com/pkg-1.0.0.tar.gz"]},
        }

    def test_dispatches_go_package(self, tmp_path):
        output = tmp_path / "out-vendor.tar.gz"
        created_tmpdir = tmp_path / "vendor-tmp"
        created_tmpdir.mkdir()
        src_dir = created_tmpdir / "src"
        meta = self._meta(["golang"])

        with patch("lib.vendor.tempfile.mkdtemp", return_value=str(created_tmpdir)), \
             patch("lib.vendor._download") as mock_download, \
             patch("lib.vendor.verify_download") as mock_verify, \
             patch("lib.vendor._extract", return_value=src_dir) as mock_extract, \
             patch("lib.vendor_golang.generate") as mock_go_generate:
            generate("test-pkg", meta, output)

        mock_download.assert_called_once()
        mock_verify.assert_called_once()
        mock_extract.assert_called_once()
        mock_go_generate.assert_called_once_with(
            "test-pkg", meta, created_tmpdir, src_dir, output, None, fedora_version=None
        )
        assert not created_tmpdir.exists()

    def test_dispatches_rust_package(self, tmp_path):
        output = tmp_path / "out-vendor.tar.gz"
        created_tmpdir = tmp_path / "vendor-tmp"
        created_tmpdir.mkdir()
        src_dir = created_tmpdir / "src"
        meta = self._meta(["cargo"])

        with patch("lib.vendor.tempfile.mkdtemp", return_value=str(created_tmpdir)), \
             patch("lib.vendor._download") as mock_download, \
             patch("lib.vendor.verify_download") as mock_verify, \
             patch("lib.vendor._extract", return_value=src_dir) as mock_extract, \
             patch("lib.vendor_rust.generate") as mock_rust_generate:
            generate("test-pkg", meta, output)

        mock_download.assert_called_once()
        mock_verify.assert_called_once()
        mock_extract.assert_called_once()
        mock_rust_generate.assert_called_once_with(
            "test-pkg", meta, created_tmpdir, src_dir, output, None, fedora_version=None
        )
        assert not created_tmpdir.exists()

    def test_both_languages_raises(self, tmp_path):
        meta = self._meta(["golang", "cargo"])
        with pytest.raises(VendorError, match="ambiguous"):
            generate("test-pkg", meta, tmp_path / "out.tar.gz")

    def test_neither_language_raises(self, tmp_path):
        meta = self._meta(["cmake"])
        with pytest.raises(VendorError, match="not a Go or Rust package"):
            generate("test-pkg", meta, tmp_path / "out.tar.gz")


class TestNoSubmoduleAccess:
    """Vendoring always downloads a hash-verified tarball into a scratch
    tmpdir; nothing here may read or write the live submodules/ checkout
    (see docs/todo.md TODO-0001, TODO-0060).
    """

    @pytest.mark.parametrize(
        "relative_path",
        ["lib/vendor.py", "lib/vendor_rust.py", "lib/vendor_golang.py", "stage-vendor.py"],
    )
    def test_module_never_mentions_submodule(self, relative_path):
        module_path = Path(__file__).parent.parent / "scripts" / relative_path
        text = module_path.read_text()
        assert "submodule" not in text.lower()


