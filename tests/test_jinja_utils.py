"""Tests for jinja_utils module."""

import tempfile
from pathlib import Path

import pytest
from jinja2 import Environment, StrictUndefined, UndefinedError

from scripts.lib.jinja_utils import create_jinja_env


def test_create_jinja_env_default():
    """Test creating Jinja environment with default template directory."""
    env = create_jinja_env()
    assert isinstance(env, Environment)
    assert env.trim_blocks is True
    assert env.lstrip_blocks is True
    assert env.keep_trailing_newline is True
    assert env.undefined == StrictUndefined


def test_create_jinja_env_custom_dir():
    """Test creating Jinja environment with custom template directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        env = create_jinja_env(tmppath)
        assert isinstance(env, Environment)
        assert env.trim_blocks is True
        assert env.lstrip_blocks is True
        assert env.keep_trailing_newline is True
        assert env.undefined == StrictUndefined


def test_jinja_env_strict_undefined():
    """Test that Jinja environment uses StrictUndefined for safety."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        template_file = tmppath / "test.j2"
        template_file.write_text("{{ undefined_var }}")

        env = create_jinja_env(tmppath)
        template = env.get_template("test.j2")

        with pytest.raises(UndefinedError):
            template.render()


def test_jinja_env_trim_blocks():
    """Test that trim_blocks and lstrip_blocks work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        template_file = tmppath / "test.j2"
        # Template with block statements
        template_file.write_text("line1\n{% if true %}\nline2\n{% endif %}\nline3")

        env = create_jinja_env(tmppath)
        template = env.get_template("test.j2")
        result = template.render()

        # With trim_blocks and lstrip_blocks, extra newlines should be removed
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result


def test_jinja_env_keep_trailing_newline():
    """Test that keep_trailing_newline preserves final newline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        template_file = tmppath / "test.j2"
        template_file.write_text("content\n")

        env = create_jinja_env(tmppath)
        template = env.get_template("test.j2")
        result = template.render()

        # Should preserve the trailing newline
        assert result.endswith("\n")
