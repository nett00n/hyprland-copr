"""Tests for scripts/set-package-release.py."""

import importlib
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

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
    """set-package-release.py imports PACKAGES_YAML as a bare name
    (`from lib.paths import PACKAGES_YAML`), so fake_repo's monkeypatch of
    lib.paths.PACKAGES_YAML alone does not redirect the script's own
    references to it -- patch the script module's copy directly.
    get_packages() itself resolves `paths.PACKAGES_YAML` at call time
    (#BUG-0079) and needs no such patch.
    """
    monkeypatch.setattr(set_package_release, "PACKAGES_YAML", fake_repo["packages_yaml"])


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

    def test_lock_before_positionals_still_recognized(self, fake_repo, monkeypatch):
        """#BUG-0082: `--lock` used to be detected by argv membership, so
        `--lock hyprlang 5` (flag first) silently treated `--lock` as the
        package-name positional instead of setting the lock."""
        _write_packages_yaml(fake_repo["packages_yaml"], "hyprlang")
        monkeypatch.setattr(
            sys, "argv", ["set-package-release.py", "--lock", "hyprlang", "5"]
        )

        set_package_release.main()

        data = yaml.safe_load(fake_repo["packages_yaml"].read_text())
        assert data["hyprlang"]["release"] == 5
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


class TestParseArgs:
    """#BUG-0082: parse_args() is real argparse, so a flag's position
    relative to the positionals never changes what gets parsed."""

    def test_flag_after_positionals(self):
        args = set_package_release.parse_args(["hyprlang", "5", "--lock"])
        assert args.packages == "hyprlang"
        assert args.release == "5"
        assert args.lock is True

    def test_flag_before_positionals(self):
        args = set_package_release.parse_args(["--lock", "hyprlang", "5"])
        assert args.packages == "hyprlang"
        assert args.release == "5"
        assert args.lock is True

    def test_missing_positional_exits_nonzero(self):
        with pytest.raises(SystemExit):
            set_package_release.parse_args(["hyprlang"])


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
