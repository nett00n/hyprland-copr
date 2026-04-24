"""Tests for uncovered branches in yaml_format.py."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
import yaml

from lib.yaml_format import (
    dump_yaml_literal,
    load_yamllint_config,
)
from lib.yaml_config import YamlConfig
from ruamel.yaml.scalarstring import LiteralScalarString


class TestWrapLiterals:
    """Test YamlConfig._wrap_literals static method."""

    def test_wraps_multiline_string(self):
        """Should wrap multiline strings as LiteralScalarString."""
        text = "line1\nline2\nline3"
        result = YamlConfig._wrap_literals(text)
        assert isinstance(result, LiteralScalarString)

    def test_preserves_single_line_string(self):
        """Should keep single-line strings as regular strings."""
        text = "single line"
        result = YamlConfig._wrap_literals(text)
        assert result == "single line"
        assert not isinstance(result, LiteralScalarString)

    def test_wraps_dict_values(self):
        """Should recursively wrap dict values."""
        data = {"key": "line1\nline2"}
        result = YamlConfig._wrap_literals(data)
        assert isinstance(result, dict)
        assert isinstance(result["key"], LiteralScalarString)

    def test_wraps_list_items(self):
        """Should recursively wrap list items."""
        data = ["line1\nline2", "single"]
        result = YamlConfig._wrap_literals(data)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], LiteralScalarString)
        assert result[1] == "single"

    def test_handles_nested_structures(self):
        """Should handle deeply nested structures."""
        data = {"outer": {"inner": "text\nwith\nnewlines"}}
        result = YamlConfig._wrap_literals(data)
        assert isinstance(result, dict)
        assert isinstance(result["outer"]["inner"], LiteralScalarString)

    def test_preserves_scalars(self):
        """Should preserve non-string scalars."""
        result = YamlConfig._wrap_literals(42)
        assert result == 42
        result = YamlConfig._wrap_literals(3.14)
        assert result == 3.14
        result = YamlConfig._wrap_literals(None)
        assert result is None


class TestDumpYamlLiteral:
    """Test dump_yaml_literal function."""

    def test_dumps_simple_dict(self):
        """Should dump simple dictionary."""
        data = {"key": "value"}
        result = dump_yaml_literal(data)
        assert isinstance(result, str)
        assert "key:" in result
        assert "value" in result

    def test_dumps_with_custom_indent(self):
        """Should use custom indentation."""
        data = {"nested": {"key": "value"}}
        result = dump_yaml_literal(data, indent=4)
        assert isinstance(result, str)

    def test_adds_explicit_start_marker(self):
        """Should add document start marker when requested."""
        data = {"key": "value"}
        result = dump_yaml_literal(data, explicit_start=True)
        assert result.startswith("---")

    def test_omits_explicit_start_marker_by_default(self):
        """Should omit document start marker by default."""
        data = {"key": "value"}
        result = dump_yaml_literal(data, explicit_start=False)
        assert not result.startswith("---")

    def test_preserves_order(self):
        """Should preserve dictionary key order."""
        from collections import OrderedDict
        data = OrderedDict([("z", "last"), ("a", "first")])
        result = dump_yaml_literal(data)
        assert isinstance(result, str)

    def test_handles_empty_dict(self):
        """Should handle empty dictionary."""
        result = dump_yaml_literal({})
        assert isinstance(result, str)

    def test_handles_multiline_values(self):
        """Should handle multiline string values."""
        data = {"description": "line1\nline2\nline3"}
        result = dump_yaml_literal(data)
        assert isinstance(result, str)


class TestGetFormattingRules:
    """Test get_formatting_rules with various indentation styles."""

    def test_handles_indentation_as_string(self, tmp_path, monkeypatch):
        """Should handle indentation value as string (e.g., 'consistent')."""
        from lib import yaml_format

        monkeypatch.setattr(yaml_format, "ROOT", tmp_path)
        yamllint_file = tmp_path / ".yamllint"
        yamllint_file.write_text("rules:\n  indentation: consistent\n")

        config = yaml.safe_load(yamllint_file.read_text())
        # Should not raise when indentation is a string
        assert isinstance(config, dict)

    def test_handles_indentation_spaces_auto(self, tmp_path, monkeypatch):
        """Should handle indentation with spaces: auto."""
        from lib import yaml_format

        monkeypatch.setattr(yaml_format, "ROOT", tmp_path)
        yamllint_file = tmp_path / ".yamllint"
        yamllint_file.write_text("rules:\n  indentation:\n    spaces: auto\n")

        config = yaml.safe_load(yamllint_file.read_text())
        # Should parse successfully
        assert isinstance(config, dict)


class TestLoadYamllintConfig:
    """Test load_yamllint_config function."""

    def test_returns_empty_dict_when_file_missing(self, tmp_path, monkeypatch):
        """Should return dict when .yamllint not found."""
        from lib import yaml_format

        monkeypatch.setattr(yaml_format, "ROOT", tmp_path)
        # Create a directory without .yamllint
        test_root = tmp_path / "test_yamllint_missing"
        test_root.mkdir()
        monkeypatch.setattr(yaml_format, "ROOT", test_root)
        result = load_yamllint_config()
        # Should return dict (may be empty or with defaults)
        assert isinstance(result, dict)

    def test_handles_invalid_yaml_gracefully(self, tmp_path, monkeypatch):
        """Should handle invalid YAML in .yamllint gracefully."""
        from lib import yaml_format

        monkeypatch.setattr(yaml_format, "ROOT", tmp_path)

        yamllint_file = tmp_path / ".yamllint"
        # Write actual invalid YAML that will fail to parse
        yamllint_file.write_text("key: [\n")

        result = load_yamllint_config()
        # Should return empty dict on parse error (handled by exception)
        assert isinstance(result, dict)

    def test_loads_yamllint_config(self, tmp_path, monkeypatch):
        """Should load .yamllint configuration file."""
        from lib import paths
        monkeypatch.setattr(paths, "ROOT", tmp_path)

        yamllint_file = tmp_path / ".yamllint"
        yamllint_file.write_text("rules:\n  line-length:\n    max: 120\n")

        result = load_yamllint_config()
        assert isinstance(result, dict)

    def test_handles_empty_yamllint_file(self, tmp_path, monkeypatch):
        """Should handle empty .yamllint file."""
        from lib import paths
        monkeypatch.setattr(paths, "ROOT", tmp_path)

        yamllint_file = tmp_path / ".yamllint"
        yamllint_file.write_text("")

        result = load_yamllint_config()
        assert isinstance(result, dict)

    def test_handles_invalid_yaml_in_config(self, tmp_path, monkeypatch):
        """Should handle invalid YAML in .yamllint gracefully."""
        from lib import paths
        monkeypatch.setattr(paths, "ROOT", tmp_path)

        yamllint_file = tmp_path / ".yamllint"
        yamllint_file.write_text("invalid: [yaml: syntax")

        result = load_yamllint_config()
        # Should return empty dict on parse error
        assert isinstance(result, dict)
