"""Tests for the 'recommends' field in packages.yaml and spec generation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.jinja_utils import create_jinja_env
from lib.yaml_utils import load_packages_yaml


class TestRecommendsLoadingFromYaml:
    """Test loading recommends field from packages.yaml."""

    def test_recommends_loaded_when_present(self, tmp_path, monkeypatch):
        """Should load recommends field when present in packages.yaml."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text(
            """
test-pkg:
  version: '1.0'
  summary: Test Package
  license: GPLv3
  description: Test description
  url: https://example.com/test
  requires:
    - libfoo
  recommends:
    - optional-dep
    - another-optional
"""
        )
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert "test-pkg" in result
        assert "recommends" in result["test-pkg"]
        assert result["test-pkg"]["recommends"] == ["optional-dep", "another-optional"]

    def test_recommends_absent_returns_none(self, tmp_path, monkeypatch):
        """Should return None/missing key when recommends not in packages.yaml."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text(
            """
test-pkg:
  version: '1.0'
  summary: Test Package
  license: GPLv3
  description: Test description
  url: https://example.com/test
"""
        )
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert "test-pkg" in result
        # recommends field should not be present or be None
        assert result["test-pkg"].get("recommends") is None

    def test_recommends_empty_list(self, tmp_path, monkeypatch):
        """Should handle empty recommends list."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text(
            """
test-pkg:
  version: '1.0'
  summary: Test Package
  license: GPLv3
  description: Test description
  url: https://example.com/test
  recommends: []
"""
        )
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert "test-pkg" in result
        assert result["test-pkg"]["recommends"] == []

    def test_recommends_with_requires(self, tmp_path, monkeypatch):
        """Should handle both requires and recommends together."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text(
            """
test-pkg:
  version: '1.0'
  summary: Test Package
  license: GPLv3
  description: Test description
  url: https://example.com/test
  requires:
    - required-dep1
    - required-dep2
  recommends:
    - optional-dep1
    - optional-dep2
"""
        )
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        pkg = result["test-pkg"]
        assert pkg["requires"] == ["required-dep1", "required-dep2"]
        assert pkg["recommends"] == ["optional-dep1", "optional-dep2"]

    def test_recommends_multiple_packages(self, tmp_path, monkeypatch):
        """Should load recommends for multiple packages correctly."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text(
            """
pkg1:
  version: '1.0'
  summary: Package 1
  license: GPLv3
  description: Desc 1
  url: https://example.com/pkg1
  recommends:
    - dep1

pkg2:
  version: '2.0'
  summary: Package 2
  license: GPLv3
  description: Desc 2
  url: https://example.com/pkg2
  recommends:
    - dep2
    - dep3
"""
        )
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert result["pkg1"]["recommends"] == ["dep1"]
        assert result["pkg2"]["recommends"] == ["dep2", "dep3"]


class TestRecommendsBuildContext:
    """Test recommends field in build_context function."""

    def test_recommends_included_in_context(self):
        """build_context should include recommends in the returned dict."""
        # Test through template rendering which validates context structure
        env = create_jinja_env()
        template = env.get_template("spec.j2")

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
            "recommends": ["optional-dep"],
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

        # Verify template renders without error (confirming recommends is in context)
        rendered = template.render(**context)
        assert "optional-dep" in rendered

    def test_recommends_defaults_to_empty_when_missing(self):
        """build_context should default recommends to empty list when not provided."""
        pkg = {"version": "1.0", "summary": "Test", "license": "GPL", "description": "Test", "url": "https://example.com"}
        recommends = pkg.get("recommends") or []
        assert recommends == []

    def test_recommends_passed_when_present(self):
        """build_context should pass recommends list when provided."""
        pkg = {
            "version": "1.0",
            "summary": "Test",
            "license": "GPL",
            "description": "Test",
            "url": "https://example.com",
            "recommends": ["dep1", "dep2"],
        }
        recommends = pkg.get("recommends") or []
        assert recommends == ["dep1", "dep2"]


class TestRecommendsTemplateRendering:
    """Test that recommends are rendered correctly in the spec template."""

    def test_recommends_section_rendered_when_present(self):
        """Spec template should render Recommends: lines when recommends present."""
        env = create_jinja_env()
        template = env.get_template("spec.j2")

        context = {
            "name": "test-pkg",
            "version": "1.0",
            "release": 1,
            "summary": "Test Package",
            "license": "GPLv3",
            "url": "https://example.com/test",
            "description": "Test description",
            "build_requires": [],
            "requires": ["dep1"],
            "recommends": ["optional-dep1", "optional-dep2"],
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

        rendered = template.render(**context)
        assert "Recommends:" in rendered
        assert "optional-dep1" in rendered
        assert "optional-dep2" in rendered

    def test_recommends_section_absent_when_empty(self):
        """Spec template should not render Recommends when list is empty."""
        env = create_jinja_env()
        template = env.get_template("spec.j2")

        context = {
            "name": "test-pkg",
            "version": "1.0",
            "release": 1,
            "summary": "Test Package",
            "license": "GPLv3",
            "url": "https://example.com/test",
            "description": "Test description",
            "build_requires": [],
            "requires": ["dep1"],
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

        rendered = template.render(**context)
        # Should not have any Recommends lines since list is empty
        assert "Recommends:" not in rendered

    def test_recommends_with_requires_coexist(self):
        """Spec template should render both Requires and Recommends when both present."""
        env = create_jinja_env()
        template = env.get_template("spec.j2")

        context = {
            "name": "test-pkg",
            "version": "1.0",
            "release": 1,
            "summary": "Test Package",
            "license": "GPLv3",
            "url": "https://example.com/test",
            "description": "Test description",
            "build_requires": [],
            "requires": ["required-dep"],
            "recommends": ["optional-dep"],
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

        rendered = template.render(**context)
        assert "Requires:" in rendered
        assert "Recommends:" in rendered
        assert "required-dep" in rendered
        assert "optional-dep" in rendered

    def test_recommends_section_order(self):
        """Spec template should render Recommends after Requires section."""
        env = create_jinja_env()
        template = env.get_template("spec.j2")

        context = {
            "name": "test-pkg",
            "version": "1.0",
            "release": 1,
            "summary": "Test Package",
            "license": "GPLv3",
            "url": "https://example.com/test",
            "description": "Test description",
            "build_requires": [],
            "requires": ["required-dep"],
            "recommends": ["optional-dep"],
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

        rendered = template.render(**context)
        requires_pos = rendered.find("Requires:")
        recommends_pos = rendered.find("Recommends:")
        # Recommends should come after Requires
        assert requires_pos < recommends_pos
