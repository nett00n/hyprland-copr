"""Tests for scripts/list-tags.py. #BUG-0078

Fakes fetch_tags/list_upstreams/resolve_module at the module boundary -- no
real network `git ls-remote` call.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

list_tags = importlib.import_module("scripts.list-tags")

cmd_list_tags = list_tags.cmd_list_tags
main = list_tags.main


class TestCmdListTags:
    def test_marks_the_detected_latest_tag(self, capsys):
        modules = [{"name": "foo", "url": "https://example.com/foo"}]
        with (
            patch.object(list_tags, "fetch_tags", return_value=(["v1.0.0", "v2.0.0"], None)),
            patch.object(list_tags, "latest_semver", return_value="v2.0.0"),
        ):
            cmd_list_tags(modules)

        out = capsys.readouterr().out
        assert "v2.0.0  <- latest" in out
        assert "v1.0.0\n" in out  # no marker on the non-latest tag

    def test_no_tags_found_message(self, capsys):
        modules = [{"name": "foo", "url": "https://example.com/foo"}]
        with (
            patch.object(list_tags, "fetch_tags", return_value=([], None)),
            patch.object(list_tags, "latest_semver", return_value=None),
        ):
            cmd_list_tags(modules)

        out = capsys.readouterr().out
        assert "(no tags found)" in out

    def test_tags_are_sorted(self, capsys):
        modules = [{"name": "foo", "url": "https://example.com/foo"}]
        with (
            patch.object(
                list_tags, "fetch_tags", return_value=(["v2.0.0", "v1.0.0", "v1.5.0"], None)
            ),
            patch.object(list_tags, "latest_semver", return_value="v2.0.0"),
        ):
            cmd_list_tags(modules)

        out = capsys.readouterr().out
        assert out.index("v1.0.0") < out.index("v1.5.0") < out.index("v2.0.0")

    def test_multiple_modules_each_printed(self, capsys):
        modules = [
            {"name": "foo", "url": "https://example.com/foo"},
            {"name": "bar", "url": "https://example.com/bar"},
        ]
        with (
            patch.object(list_tags, "fetch_tags", return_value=(["v1.0.0"], None)),
            patch.object(list_tags, "latest_semver", return_value="v1.0.0"),
        ):
            cmd_list_tags(modules)

        out = capsys.readouterr().out
        assert "foo" in out
        assert "bar" in out


class TestMain:
    def test_missing_packages_yaml_exits(self, monkeypatch, tmp_path):
        monkeypatch.setattr(list_tags, "PACKAGES_YAML", tmp_path / "nonexistent")
        with patch.object(sys, "argv", ["list-tags.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_unknown_package_exits(self, monkeypatch, tmp_path):
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(list_tags, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(list_tags, "get_packages", lambda path: {})
        with (
            patch.object(list_tags, "list_upstreams", return_value=[]),
            patch.object(list_tags, "resolve_module", return_value=None),
            patch.object(sys, "argv", ["list-tags.py", "nonexistent-pkg"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_single_package_resolves_and_lists(self, monkeypatch, tmp_path, capsys):
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(list_tags, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(list_tags, "get_packages", lambda path: {})
        mod = {"name": "foo", "url": "https://example.com/foo"}
        with (
            patch.object(list_tags, "list_upstreams", return_value=[mod]),
            patch.object(list_tags, "resolve_module", return_value=mod),
            patch.object(list_tags, "fetch_tags", return_value=(["v1.0.0"], None)),
            patch.object(list_tags, "latest_semver", return_value="v1.0.0"),
            patch.object(sys, "argv", ["list-tags.py", "foo"]),
        ):
            main()

        out = capsys.readouterr().out
        assert "foo" in out

    def test_no_package_arg_lists_all_modules(self, monkeypatch, tmp_path, capsys):
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(list_tags, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(list_tags, "get_packages", lambda path: {})
        modules = [
            {"name": "foo", "url": "https://example.com/foo"},
            {"name": "bar", "url": "https://example.com/bar"},
        ]
        with (
            patch.object(list_tags, "list_upstreams", return_value=modules),
            patch.object(list_tags, "fetch_tags", return_value=([], None)),
            patch.object(list_tags, "latest_semver", return_value=None),
            patch.object(sys, "argv", ["list-tags.py"]),
        ):
            main()

        out = capsys.readouterr().out
        assert "foo" in out
        assert "bar" in out
