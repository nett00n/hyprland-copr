"""Tests for the 'conflicts' / 'provides' fields in spec generation (#COPR-0005)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.jinja_utils import create_jinja_env  # noqa: E402
from lib.validation import validate_field_types  # noqa: E402


def _context(**overrides):
    context = {
        "name": "test-pkg",
        "version": "1.0",
        "release": 1,
        "summary": "Test Package",
        "license": "GPLv3",
        "url": "https://example.com/test",
        "description": "Test description",
        "build_requires": [],
        "requires": [],
        "recommends": [],
        "sources": [],
        "patches": [],
        "bundled_deps": [],
        "prep_commands": [],
        "build_cmd": "%cmake",
        "install_cmd": "%cmake_install",
        "files": ["%{_bindir}/test-pkg"],
        "no_debug_package": False,
        "no_lto": False,
        "commit": None,
        "buildarch": None,
        "source_name": "test-pkg",
        "source_dir": None,
        "changelog": {
            "date": "Mon Jan 01 2025",
            "packager": "Test User <test@example.com>",
            "version": "1.0",
            "release": 1,
            "notes": ["Initial release"],
            "source_url": None,
            "copr_url": None,
            "tag": None,
            "commit": None,
        },
        "devel": None,
        "dep_versions": [],
        "project_packages": [],
    }
    context.update(overrides)
    return context


def _render(**overrides):
    return create_jinja_env().get_template("spec.j2").render(**_context(**overrides))


class TestSpecRendering:
    def test_conflicts_and_provides_rendered(self):
        rendered = _render(conflicts=["swaylock"], provides=["swaylock"])
        assert "Conflicts:      swaylock" in rendered
        assert "Provides:       swaylock" in rendered

    def test_multiple_entries_one_line_each(self):
        rendered = _render(conflicts=["a", "b"])
        assert "Conflicts:      a" in rendered
        assert "Conflicts:      b" in rendered

    def test_absent_renders_nothing(self):
        rendered = _render()
        assert "Conflicts:" not in rendered
        assert "Provides:" not in rendered

    def test_empty_lists_render_nothing(self):
        rendered = _render(conflicts=[], provides=[])
        assert "Conflicts:" not in rendered
        assert "Provides:" not in rendered


class TestValidation:
    @pytest.mark.parametrize("field", ["conflicts", "provides"])
    def test_list_accepted(self, field):
        errors, _ = validate_field_types("pkg", {field: ["swaylock"]})
        assert not errors

    @pytest.mark.parametrize("field", ["conflicts", "provides"])
    def test_non_list_rejected(self, field):
        errors, _ = validate_field_types("pkg", {field: "swaylock"})
        assert any(field in e for e in errors)
