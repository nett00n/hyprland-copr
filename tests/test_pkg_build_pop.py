"""Tests for scripts/pkg-build-pop.py."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths  # noqa: E402

pkg_build_pop = importlib.import_module("scripts.pkg-build-pop")

_PKG_TEMPLATE = """{name}:
  version: "1.0"
  license: MIT
  summary: s
  description: d
  url: https://example.com
  source:
    archives: ["https://example.com/{name}.tar.gz"]
  build:
    system: cmake
"""


def _write_packages_yaml(root, *names):
    (root / "packages.yaml").write_text(
        "".join(_PKG_TEMPLATE.format(name=name) for name in names)
    )


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed_mock_copr_rows(target, packages):
    run_id = build_db.start_run(target, "fedora", "44", "x86_64")
    for pkg in packages:
        build_db.set_stage(pkg, "mock", target, run_id, "success")
        build_db.set_stage(pkg, "copr", target, run_id, "success")


class TestMainClearsSelectedPackages:
    def test_no_package_env_clears_every_package(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        target = "fedora-44-x86_64"
        _seed_mock_copr_rows(target, ["valid-pkg"])
        monkeypatch.delenv("PACKAGE", raising=False)
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        pkg_build_pop.main()

        out = capsys.readouterr().out
        assert "cleared mock/copr for: valid-pkg" in out
        assert build_db.get_stage("valid-pkg", "mock", target)["force_run"] == 1
        assert build_db.get_stage("valid-pkg", "copr", target)["force_run"] == 1

    def test_comma_separated_package_clears_only_those(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["root"], "valid-pkg", "other-pkg")
        target = "fedora-44-x86_64"
        _seed_mock_copr_rows(target, ["valid-pkg", "other-pkg"])
        monkeypatch.setenv("PACKAGE", "valid-pkg")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        pkg_build_pop.main()

        assert build_db.get_stage("valid-pkg", "mock", target)["force_run"] == 1
        assert build_db.get_stage("other-pkg", "mock", target)["force_run"] == 0

    def test_case_insensitive_package_name_resolution(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["root"], "Valid-Pkg")
        target = "fedora-44-x86_64"
        _seed_mock_copr_rows(target, ["Valid-Pkg"])
        monkeypatch.setenv("PACKAGE", "valid-pkg")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        pkg_build_pop.main()

        out = capsys.readouterr().out
        assert "Valid-Pkg" in out


class TestMainErrorsAndNoOps:
    def test_unknown_package_exits_nonzero_naming_it(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        monkeypatch.setenv("PACKAGE", "nonexistent-pkg")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            pkg_build_pop.main()

        assert "nonexistent-pkg" in str(exc_info.value)

    def test_nothing_to_clear_when_rows_already_empty(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        monkeypatch.setenv("PACKAGE", "valid-pkg")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        pkg_build_pop.main()

        out = capsys.readouterr().out
        assert "nothing to clear" in out

    def test_whitespace_only_package_env_is_nothing_to_do(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        monkeypatch.setenv("PACKAGE", " , ,")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            pkg_build_pop.main()

        assert exc_info.value.code == 0
        assert "nothing to do" in capsys.readouterr().err


class TestTargetResolution:
    def test_fedora_version_default_is_44(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        target = "fedora-44-x86_64"
        _seed_mock_copr_rows(target, ["valid-pkg"])
        monkeypatch.delenv("PACKAGE", raising=False)
        monkeypatch.delenv("FEDORA_VERSION", raising=False)
        monkeypatch.delenv("MOCK_CHROOT", raising=False)

        pkg_build_pop.main()

        assert build_db.get_stage("valid-pkg", "mock", target)["force_run"] == 1

    def test_mock_chroot_override_reaches_set_force_run(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["root"], "valid-pkg")
        target = "custom-chroot-x86_64"
        _seed_mock_copr_rows(target, ["valid-pkg"])
        monkeypatch.setenv("PACKAGE", "valid-pkg")
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.setenv("MOCK_CHROOT", "custom-chroot-x86_64")

        pkg_build_pop.main()

        assert build_db.get_stage("valid-pkg", "mock", target)["force_run"] == 1
