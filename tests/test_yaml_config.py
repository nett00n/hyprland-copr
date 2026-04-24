"""Tests for scripts/lib/yaml_config.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import yaml
import pytest

from lib.yaml_config import YamlConfig, FORMAT_FILE, DEFAULT, _NO_WRAP_WIDTH


class TestYamlConfigDump:
    """Test YamlConfig.dump() round-trip and data preservation."""

    def test_round_trip_simple(self):
        """Flat dict should round-trip through dump → yaml.safe_load."""
        data = {"name": "test", "version": "1.0", "enabled": True}
        cfg = YamlConfig()
        dumped = cfg.dump(data)
        loaded = yaml.safe_load(dumped)
        assert loaded == data

    def test_round_trip_nested(self):
        """Nested dict with list should round-trip correctly."""
        data = {
            "pkg": {
                "version": "2.0",
                "requires": ["dep1", "dep2"],
                "metadata": {"author": "test", "tags": ["a", "b"]},
            }
        }
        cfg = YamlConfig()
        dumped = cfg.dump(data)
        loaded = yaml.safe_load(dumped)
        assert loaded == data

    def test_special_values_preserved(self):
        """None, True, False, integers should round-trip as correct Python types."""
        data = {
            "none_val": None,
            "bool_true": True,
            "bool_false": False,
            "number": 42,
            "float_val": 3.14,
        }
        cfg = YamlConfig()
        dumped = cfg.dump(data)
        loaded = yaml.safe_load(dumped)
        assert loaded["none_val"] is None
        assert loaded["bool_true"] is True
        assert loaded["bool_false"] is False
        assert loaded["number"] == 42
        assert loaded["float_val"] == 3.14

    def test_yaml_special_chars_in_strings(self):
        """Strings with colons, quotes should not break YAML parsing."""
        data = {
            "url": "http://example.com:8080",
            "quoted": 'He said "hello"',
            "with_colon": "key: value",
        }
        cfg = YamlConfig()
        dumped = cfg.dump(data)
        loaded = yaml.safe_load(dumped)
        assert loaded["url"] == "http://example.com:8080"
        assert loaded["quoted"] == 'He said "hello"'
        assert loaded["with_colon"] == "key: value"

    def test_explicit_start_true_adds_marker(self):
        """explicit_start=True should start output with ---."""
        cfg = YamlConfig(explicit_start=True)
        dumped = cfg.dump({"key": "value"})
        assert dumped.startswith("---")

    def test_explicit_start_false_no_marker(self):
        """explicit_start=False should not start with ---."""
        cfg = YamlConfig(explicit_start=False)
        dumped = cfg.dump({"key": "value"})
        assert not dumped.startswith("---")


class TestFormatFileFactory:
    """Test FORMAT_FILE factory function."""

    def test_returns_yamlconfig_instance(self):
        """FORMAT_FILE should return a YamlConfig instance."""
        cfg = FORMAT_FILE(2, False)
        assert isinstance(cfg, YamlConfig)

    def test_explicit_start_true(self):
        """FORMAT_FILE with explicit_start=True should produce --- marker."""
        cfg = FORMAT_FILE(2, True)
        dumped = cfg.dump({"x": 1})
        assert dumped.startswith("---")

    def test_explicit_start_false(self):
        """FORMAT_FILE with explicit_start=False should not have --- marker."""
        cfg = FORMAT_FILE(2, False)
        dumped = cfg.dump({"x": 1})
        assert not dumped.startswith("---")

    def test_indent_4(self):
        """FORMAT_FILE with indent=4 should produce 4-space indentation."""
        cfg = FORMAT_FILE(4, False)
        dumped = cfg.dump({"root": {"nested": "value"}})
        lines = dumped.split("\n")
        for line in lines:
            if line and line[0] == " ":
                spaces = len(line) - len(line.lstrip(" "))
                assert spaces % 4 == 0, f"Expected 4-space indent, got: {repr(line)}"

    def test_no_wrap_width(self):
        """FORMAT_FILE should always use _NO_WRAP_WIDTH."""
        cfg = FORMAT_FILE(2, False)
        assert cfg.width == _NO_WRAP_WIDTH


class TestYamlConfigDefault:
    """Test DEFAULT singleton configuration."""

    def test_default_attributes(self):
        """DEFAULT should have correct attributes."""
        assert DEFAULT.indent == 2
        assert DEFAULT.explicit_start is False
        assert DEFAULT.offset == 0
        assert DEFAULT.width == _NO_WRAP_WIDTH

    def test_default_no_document_marker(self):
        """DEFAULT.dump() should not include --- marker."""
        dumped = DEFAULT.dump({"x": 1})
        assert not dumped.startswith("---")
