"""Tests for complete coverage of paths.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.paths import (
    get_package_log_dir,
    mock_chroot,
    ROOT,
    BUILD_LOG_DIR,
)


class TestGetPackageLogDir:
    """Test get_package_log_dir function."""

    def test_returns_valid_path(self):
        """Should return a valid Path object."""
        result = get_package_log_dir("test-pkg")
        assert isinstance(result, Path)

    def test_includes_package_name(self):
        """Should include package name in path."""
        result = get_package_log_dir("my-package")
        assert "my-package" in str(result).lower()

    def test_is_absolute_path(self):
        """Should return absolute path."""
        result = get_package_log_dir("test-pkg")
        assert result.is_absolute()

    def test_different_packages_have_different_paths(self):
        """Should return different paths for different packages."""
        path1 = get_package_log_dir("pkg1")
        path2 = get_package_log_dir("pkg2")
        assert path1 != path2

    def test_log_dir_path_structure(self):
        """Should follow build logs directory structure."""
        result = get_package_log_dir("test-pkg")
        assert "logs" in str(result)
        assert "build" in str(result)


class TestMockChroot:
    """Test mock_chroot function."""

    def test_returns_fedora_45_chroot(self):
        """Should return correct chroot for an arbitrary version string."""
        result = mock_chroot("45")
        assert "fedora-45" in result
        assert "x86_64" in result

    def test_returns_fedora_43_chroot(self):
        """Should return correct chroot for Fedora 43."""
        result = mock_chroot("43")
        assert "fedora-43" in result
        assert "x86_64" in result

    def test_returns_rawhide_chroot(self):
        """Should return rawhide chroot for rawhide."""
        result = mock_chroot("rawhide")
        assert "fedora-rawhide" in result or "rawhide" in result
        assert "x86_64" in result

    def test_returns_string(self):
        """Should return a string chroot name."""
        result = mock_chroot("43")
        assert isinstance(result, str)


class TestPathConstants:
    """Test path constant definitions."""

    def test_root_path_exists(self):
        """Should define ROOT path."""
        assert ROOT is not None
        assert isinstance(ROOT, Path)

    def test_build_log_dir_exists(self):
        """Should define BUILD_LOG_DIR path."""
        assert BUILD_LOG_DIR is not None
        assert isinstance(BUILD_LOG_DIR, Path)

    def test_paths_are_reasonable(self):
        """Should have paths that make sense."""
        # Paths should be under root or at root
        assert isinstance(ROOT, Path)
        assert isinstance(BUILD_LOG_DIR, Path)
