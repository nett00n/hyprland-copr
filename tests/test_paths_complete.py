"""Tests for complete coverage of paths.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.paths import (
    get_package_log_dir,
    get_run_log_dir,
    iter_package_log_dirs,
    mock_chroot,
    local_repo,
    host_path,
    ROOT,
    RUNS_LOG_DIR,
    LOCAL_REPO_ROOT,
)


class TestGetRunLogDir:
    """#COPR-0022: get_run_log_dir()."""

    def test_returns_valid_path(self):
        result = get_run_log_dir(7, "fedora-44-x86_64")
        assert isinstance(result, Path)

    def test_nests_under_run_id_then_target(self):
        result = get_run_log_dir(7, "fedora-44-x86_64")
        assert result == RUNS_LOG_DIR / "7" / "fedora-44-x86_64"

    def test_rejects_path_traversal_in_target(self):
        with pytest.raises(ValueError):
            get_run_log_dir(7, "../../etc")

    def test_rejects_path_separator_in_target(self):
        with pytest.raises(ValueError):
            get_run_log_dir(7, "a/b")


class TestGetPackageLogDir:
    """#COPR-0022: get_package_log_dir() is scoped by run_id and target."""

    def test_returns_valid_path(self):
        """Should return a valid Path object."""
        result = get_package_log_dir("test-pkg", 1, "fedora-44-x86_64")
        assert isinstance(result, Path)

    def test_includes_package_name(self):
        """Should include package name in path."""
        result = get_package_log_dir("my-package", 1, "fedora-44-x86_64")
        assert "my-package" in str(result).lower()

    def test_is_absolute_path(self):
        """Should return absolute path."""
        result = get_package_log_dir("test-pkg", 1, "fedora-44-x86_64")
        assert result.is_absolute()

    def test_different_packages_have_different_paths(self):
        """Should return different paths for different packages."""
        path1 = get_package_log_dir("pkg1", 1, "fedora-44-x86_64")
        path2 = get_package_log_dir("pkg2", 1, "fedora-44-x86_64")
        assert path1 != path2

    def test_same_package_different_targets_same_run_dont_collide(self):
        """#COPR-0022's named collision: two chroots of the same package in one
        matrix run must not overwrite each other's logs."""
        x86 = get_package_log_dir("pkg", 5, "fedora-44-x86_64")
        aarch64 = get_package_log_dir("pkg", 5, "fedora-44-aarch64")
        assert x86 != aarch64

    def test_same_package_target_different_run_dont_collide(self):
        """A rebuild in a later run must not overwrite the earlier run's logs."""
        run1 = get_package_log_dir("pkg", 1, "fedora-44-x86_64")
        run2 = get_package_log_dir("pkg", 2, "fedora-44-x86_64")
        assert run1 != run2

    def test_log_dir_path_structure(self):
        """Should nest under logs/runs/<run_id>/<target>/<package>."""
        result = get_package_log_dir("test-pkg", 3, "fedora-44-x86_64")
        assert result == RUNS_LOG_DIR / "3" / "fedora-44-x86_64" / "test-pkg"


class TestIterPackageLogDirs:
    """#COPR-0022: iter_package_log_dirs() -- delete-package.py's discovery."""

    def test_empty_when_runs_dir_missing(self, tmp_path, monkeypatch):
        import lib.paths as paths_module

        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
        assert iter_package_log_dirs("pkg") == []

    def test_finds_across_runs_and_targets(self, tmp_path, monkeypatch):
        import lib.paths as paths_module

        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        (runs_dir / "1" / "fedora-43-x86_64" / "pkg").mkdir(parents=True)
        (runs_dir / "2" / "fedora-44-x86_64" / "pkg").mkdir(parents=True)
        (runs_dir / "2" / "fedora-44-x86_64" / "other-pkg").mkdir(parents=True)

        result = iter_package_log_dirs("pkg")

        assert len(result) == 2
        assert all(p.name == "pkg" for p in result)


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


class TestLocalRepo:
    """Test local_repo() -- the per-chroot dnf repo dir mock resolves build deps against."""

    def test_scoped_under_local_repo_root(self):
        """Should nest under LOCAL_REPO_ROOT, keyed by target."""
        result = local_repo("fedora-44-x86_64")
        assert result == LOCAL_REPO_ROOT / "fedora-44-x86_64"

    def test_different_targets_get_different_dirs(self):
        """Should isolate fedora-43 from fedora-44 -- the whole point of scoping."""
        assert local_repo("fedora-43-x86_64") != local_repo("fedora-44-x86_64")

    def test_works_with_mock_chroot_output(self):
        """Should accept whatever mock_chroot()/resolve_target() produces, incl. rawhide."""
        result = local_repo(mock_chroot("rawhide"))
        assert result == LOCAL_REPO_ROOT / "fedora-rawhide-x86_64"

    def test_returns_path_under_root(self):
        """Should stay inside the repo checkout."""
        result = local_repo("fedora-44-x86_64")
        assert result.is_relative_to(ROOT)

    def test_rejects_path_traversal(self):
        """Should refuse a target that would escape LOCAL_REPO_ROOT."""
        with pytest.raises(ValueError):
            local_repo("../../etc")

    def test_rejects_path_separator(self):
        """Should refuse a target containing a path separator."""
        with pytest.raises(ValueError):
            local_repo("a/b")

    def test_local_repo_constant_no_longer_exported(self):
        """The old shared, unscoped LOCAL_REPO constant must be gone -- a leftover alias
        would let a caller silently keep writing to it."""
        import lib.paths as paths_module

        assert not hasattr(paths_module, "LOCAL_REPO")


class TestPathConstants:
    """Test path constant definitions."""

    def test_root_path_exists(self):
        """Should define ROOT path."""
        assert ROOT is not None
        assert isinstance(ROOT, Path)

    def test_runs_log_dir_exists(self):
        """Should define RUNS_LOG_DIR path."""
        assert RUNS_LOG_DIR is not None
        assert isinstance(RUNS_LOG_DIR, Path)

    def test_paths_are_reasonable(self):
        """Should have paths that make sense."""
        # Paths should be under root or at root
        assert isinstance(ROOT, Path)
        assert isinstance(RUNS_LOG_DIR, Path)


class TestHostPath:
    """#COPR-0015, #BUG-0062: host_path()."""

    def test_rpmbuild_volume_realm_returns_none(self):
        assert host_path("rpmbuild-volume", "/root/rpmbuild/SRPMS/pkg.src.rpm") is None

    def test_repo_realm_strips_container_prefix(self):
        assert host_path("repo", "/work/local-repo/fedora-44-x86_64/pkg.rpm") == (
            ROOT / "local-repo" / "fedora-44-x86_64" / "pkg.rpm"
        )

    def test_vendor_store_realm_strips_container_prefix(self):
        assert host_path("vendor-store", "/work/.cache/vendor/pkg/abc/tarball.tar.gz") == (
            ROOT / ".cache" / "vendor" / "pkg" / "abc" / "tarball.tar.gz"
        )

    def test_already_relative_path_resolves_against_root(self):
        """stage-mock.py's mock-log rows are already repo-relative."""
        assert host_path("repo", "logs/runs/7/fedora-44-x86_64/pkg/21-mock-build.log") == (
            ROOT / "logs" / "runs" / "7" / "fedora-44-x86_64" / "pkg" / "21-mock-build.log"
        )

    def test_absolute_path_outside_container_mount_returned_unchanged(self):
        """Already host-resolved (e.g. this call running outside a container)."""
        assert host_path("repo", "/some/other/absolute/path.rpm") == Path(
            "/some/other/absolute/path.rpm"
        )

    def test_unknown_realm_returns_none(self):
        assert host_path("unknown-realm", "/work/x") is None
