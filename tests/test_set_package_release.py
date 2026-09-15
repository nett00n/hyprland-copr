"""Tests for scripts/set-package-release.py."""

import importlib
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.yaml_utils import get_packages as _real_get_packages  # noqa: E402

set_package_release = importlib.import_module("scripts.set-package-release")

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


def _write_packages_yaml(path, *names):
    path.write_text("".join(_PKG_TEMPLATE.format(name=name) for name in names))


@pytest.fixture(autouse=True)
def _redirect_paths(fake_repo, monkeypatch):
    """PACKAGES_YAML and get_packages() are value/default-arg imports bound at
    module-import time in set-package-release.py, so fake_repo's monkeypatch of
    lib.paths.PACKAGES_YAML alone does not redirect them (docs/TODO.md
    BUG-0079). Patch the script module's own references.
    """
    monkeypatch.setattr(set_package_release, "PACKAGES_YAML", fake_repo["packages_yaml"])
    monkeypatch.setattr(
        set_package_release,
        "get_packages",
        lambda: _real_get_packages(fake_repo["packages_yaml"]),
    )


class TestSetsRelease:
    def test_single_package(self, fake_repo, monkeypatch, capsys):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "5"])

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["hyprlang"]["release"] == 5
        assert "Set hyprlang: release=5" in capsys.readouterr().out

    def test_comma_separated_packages(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang", "hyprutils")
        monkeypatch.setattr(
            sys, "argv", ["set-package-release.py", "hyprlang,hyprutils", "5"]
        )

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["hyprlang"]["release"] == 5
        assert data["hyprutils"]["release"] == 5

    def test_case_insensitive_resolution(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "Hyprlang")
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "5"])

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["Hyprlang"]["release"] == 5


class TestLockFlag:
    def test_lock_sets_release_lock_true(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(
            sys, "argv", ["set-package-release.py", "hyprlang", "5", "--lock"]
        )

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["hyprlang"]["release_lock"] is True

    def test_omitting_lock_removes_existing_lock(self, fake_repo, monkeypatch):
        fake_repo["packages_yaml"].write_text(
            "hyprlang:\n"
            "  version: \"1.0\"\n"
            "  license: MIT\n"
            "  summary: s\n"
            "  description: d\n"
            "  url: https://example.com\n"
            "  release: 3\n"
            "  release_lock: true\n"
            "  source:\n"
            "    archives: [\"https://example.com/hyprlang.tar.gz\"]\n"
            "  build:\n"
            "    system: cmake\n"
        )
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "5"])

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["hyprlang"]["release"] == 5
        assert "release_lock" not in data["hyprlang"]


class TestValidationErrors:
    def test_non_integer_release_exits_nonzero(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "abc"])

        with pytest.raises(SystemExit):
            set_package_release.main()

    def test_negative_release_exits_nonzero(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "-1"])

        with pytest.raises(SystemExit):
            set_package_release.main()

    def test_unknown_package_exits_nonzero(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(
            sys, "argv", ["set-package-release.py", "nonexistent", "5"]
        )

        with pytest.raises(SystemExit) as exc_info:
            set_package_release.main()

        assert "nonexistent" in str(exc_info.value)

    def test_empty_package_list_exits_nonzero(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", " , ", "5"])

        with pytest.raises(SystemExit):
            set_package_release.main()

    def test_too_few_args_exits_nonzero(self, fake_repo, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang"])

        with pytest.raises(SystemExit):
            set_package_release.main()


class TestUnrelatedPackagesUntouched:
    def test_other_packages_unchanged(self, fake_repo, monkeypatch):
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang", "hyprutils")
        before = yaml.safe_load(fake_repo["packages_yaml"].read_text())["hyprutils"]
        monkeypatch.setattr(sys, "argv", ["set-package-release.py", "hyprlang", "5"])

        set_package_release.main()

        after = yaml.safe_load(fake_repo["packages_yaml"].read_text())["hyprutils"]
        assert after == before
