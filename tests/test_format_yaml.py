"""Tests for scripts/format-yaml.py."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

format_yaml = importlib.import_module("scripts.format-yaml")


class TestLoadYamllintConfig:
    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        assert format_yaml.load_yamllint_config() == {}

    def test_valid_config_parsed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        (tmp_path / ".yamllint").write_text("rules:\n  indentation:\n    spaces: 4\n")

        config = format_yaml.load_yamllint_config()

        assert config["rules"]["indentation"]["spaces"] == 4

    def test_malformed_yaml_warns_and_returns_empty_dict(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        (tmp_path / ".yamllint").write_text("{ not: valid: yaml")

        config = format_yaml.load_yamllint_config()

        assert config == {}
        assert "Warning" in capsys.readouterr().err


class TestGetIgnoredFiles:
    def test_absent_ignore_key_returns_empty_set(self):
        assert format_yaml.get_ignored_files({}) == set()

    def test_newline_delimited_block_parsed(self):
        config = {"ignore": "a.yaml\nb.yaml\n"}
        assert format_yaml.get_ignored_files(config) == {"a.yaml", "b.yaml"}

    def test_non_string_ignore_value_warns_and_returns_empty_set(self, capsys):
        config = {"ignore": ["a.yaml"]}

        result = format_yaml.get_ignored_files(config)

        assert result == set()
        assert "Warning" in capsys.readouterr().err


class TestGetFormattingRules:
    """#BUG-0081: get_formatting_rules() used to also compute an
    `indent_spaces` key from the `indentation` rule, but format_yaml_file()
    has always used detect_indentation(content) instead -- that config path
    was dead and has been dropped, not wired in."""

    def test_indent_spaces_not_in_returned_rules(self):
        rules = format_yaml.get_formatting_rules(
            {"rules": {"indentation": {"spaces": 2}}}
        )
        assert "indent_spaces" not in rules

    def test_document_start_level_sets_explicit_start_true(self):
        rules = format_yaml.get_formatting_rules(
            {"rules": {"document-start": {"level": "error"}}}
        )
        assert rules["explicit_start"] is True

    def test_document_start_absent_sets_explicit_start_false(self):
        rules = format_yaml.get_formatting_rules({})
        assert rules["explicit_start"] is False


class TestDetectIndentation:
    def test_two_space_indentation(self):
        content = "key:\n  child: value\n"
        assert format_yaml.detect_indentation(content) == 2

    def test_four_space_indentation(self):
        content = "key:\n    child: value\n"
        assert format_yaml.detect_indentation(content) == 4

    def test_no_indentation_defaults_to_2(self):
        content = "key: value\nother: value\n"
        assert format_yaml.detect_indentation(content) == 2

    def test_skips_list_item_lines(self):
        content = "key:\n- item1\n    nested: value\n"
        assert format_yaml.detect_indentation(content) == 4


class TestFormatYamlFile:
    def test_round_trips_valid_file(self, tmp_path):
        f = tmp_path / "x.yaml"
        f.write_text("key: value\nlist:\n  - a\n  - b\n")

        ok = format_yaml.format_yaml_file(str(f), {"indent_spaces": 2, "explicit_start": False})

        assert ok is True
        assert f.read_text().endswith("\n")

    def test_empty_file_is_noop_returning_true(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")

        ok = format_yaml.format_yaml_file(str(f), {"indent_spaces": 2, "explicit_start": False})

        assert ok is True
        assert f.read_text() == ""

    def test_unparseable_yaml_returns_false_without_clobbering(self, tmp_path):
        f = tmp_path / "bad.yaml"
        original = "{ not: valid: yaml"
        f.write_text(original)

        ok = format_yaml.format_yaml_file(str(f), {"indent_spaces": 2, "explicit_start": False})

        assert ok is False
        assert f.read_text() == original

    def test_trailing_spaces_removed(self, tmp_path):
        f = tmp_path / "x.yaml"
        f.write_text("key: value\n")

        format_yaml.format_yaml_file(str(f), {"indent_spaces": 2, "explicit_start": False})

        assert not any(line.endswith(" ") for line in f.read_text().split("\n"))


class TestMain:
    def test_no_glob_match_returns_1(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["format-yaml.py", "*.nomatch"])

        assert format_yaml.main() == 1
        assert "No files matching pattern" in capsys.readouterr().err

    def test_formats_matching_files_and_returns_0(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        (tmp_path / "a.yaml").write_text("key: value\n")
        monkeypatch.setattr(sys, "argv", ["format-yaml.py", "*.yaml"])

        assert format_yaml.main() == 0
        assert "Formatted 1 file(s)" in capsys.readouterr().out

    def test_ignored_files_are_skipped(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        (tmp_path / ".yamllint").write_text("ignore: |\n  skip.yaml\n")
        (tmp_path / "skip.yaml").write_text("key:   value\n")
        original = (tmp_path / "skip.yaml").read_text()
        monkeypatch.setattr(sys, "argv", ["format-yaml.py", "*.yaml"])

        format_yaml.main()

        assert (tmp_path / "skip.yaml").read_text() == original

    def test_failed_files_return_1(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(format_yaml, "ROOT", tmp_path)
        (tmp_path / "bad.yaml").write_text("{ not: valid: yaml")
        monkeypatch.setattr(sys, "argv", ["format-yaml.py", "*.yaml"])

        assert format_yaml.main() == 1
        assert "Failed to format" in capsys.readouterr().err
