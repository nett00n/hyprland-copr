"""Tests for uncovered branches in validation.py."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.validation import (
    validate_package,
    validate_no_duplicate_urls,
    REQUIRED_FIELDS,
    VALID_BUILD_SYSTEMS,
)


class TestValidatePackage:
    """Test validate_package function."""

    def get_minimal_package(self):
        """Return minimal valid package for testing."""
        return {
            "version": "1.0",
            "license": "MIT",
            "summary": "Test package",
            "description": "A test package",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/pkg-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }

    def test_validates_correct_package(self):
        """Should validate correct package without errors."""
        meta = self.get_minimal_package()
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert errors == []

    def test_detects_missing_version(self):
        """Should detect missing version."""
        meta = self.get_minimal_package()
        del meta["version"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("version" in e.lower() for e in errors)

    def test_detects_missing_license(self):
        """Should detect missing license."""
        meta = self.get_minimal_package()
        del meta["license"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("license" in e.lower() for e in errors)

    def test_detects_missing_summary(self):
        """Should detect missing summary."""
        meta = self.get_minimal_package()
        del meta["summary"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("summary" in e.lower() for e in errors)

    def test_detects_missing_description(self):
        """Should detect missing description."""
        meta = self.get_minimal_package()
        del meta["description"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("description" in e.lower() for e in errors)

    def test_detects_missing_url(self):
        """Should detect missing URL."""
        meta = self.get_minimal_package()
        del meta["url"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("url" in e.lower() for e in errors)

    def test_detects_missing_source_archives(self):
        """Should detect missing source archives."""
        meta = self.get_minimal_package()
        del meta["source"]["archives"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("archives" in e.lower() for e in errors)

    def test_detects_deprecated_debuginfo_section(self):
        """Should detect deprecated debuginfo section."""
        meta = self.get_minimal_package()
        meta["debuginfo"] = {"depends": []}
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("debuginfo" in e.lower() for e in errors)

    def test_detects_invalid_build_system(self):
        """Should detect invalid build system."""
        meta = self.get_minimal_package()
        meta["build"]["system"] = "invalid_system"
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("invalid" in e.lower() and "build" in e.lower() for e in errors)

    def test_allows_valid_build_systems(self):
        """Should accept all valid build systems."""
        all_packages = {}

        for build_sys in VALID_BUILD_SYSTEMS:
            meta = self.get_minimal_package()
            meta["build"]["system"] = build_sys
            all_packages["test-" + build_sys] = meta

            errors, warnings = validate_package("test-" + build_sys, meta, all_packages)
            # Errors may exist for other reasons, but not for invalid build system
            assert not any("invalid" in e.lower() and "build" in e.lower() for e in errors)

    def test_allows_fixme_build_system(self):
        """Should allow FIXME as build system."""
        meta = self.get_minimal_package()
        meta["build"]["system"] = "FIXME"
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should not have errors about invalid build system
        assert not any("invalid" in e.lower() and "build" in e.lower() for e in errors)

    def test_warns_devel_files_in_main(self):
        """Should warn when devel files are in main files section."""
        meta = self.get_minimal_package()
        meta["files"] = ["%{_includedir}/header.h"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("devel" in w.lower() for w in warnings)

    def test_warns_pkgconfig_in_main(self):
        """Should warn when pkgconfig files are in main files section."""
        meta = self.get_minimal_package()
        meta["files"] = ["/usr/lib/pkgconfig/test.pc"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("devel" in w.lower() for w in warnings)

    def test_warns_cmake_files_in_main(self):
        """Should warn when cmake files are in main files section."""
        meta = self.get_minimal_package()
        meta["files"] = ["/usr/lib/cmake/Test.cmake"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("devel" in w.lower() for w in warnings)

    def test_detects_invalid_dependency_reference(self):
        """Should detect reference to non-existent dependency."""
        meta = self.get_minimal_package()
        meta["depends_on"] = ["nonexistent-pkg"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("nonexistent" in e.lower() or "unknown" in e.lower() for e in errors)

    def test_allows_valid_dependency_reference(self):
        """Should allow reference to existing dependency."""
        meta1 = self.get_minimal_package()
        meta2 = self.get_minimal_package()
        meta2["depends_on"] = ["dep-pkg"]

        all_packages = {
            "test-pkg": meta2,
            "dep-pkg": meta1,
        }

        errors, warnings = validate_package("test-pkg", meta2, all_packages)

        # May have other errors, but not about invalid dependency
        assert not any("unknown" in e.lower() and "depend" in e.lower() for e in errors)

    def test_detects_case_insensitive_dependency_reference(self):
        """Should handle case-insensitive dependency lookup."""
        meta1 = self.get_minimal_package()
        meta2 = self.get_minimal_package()
        meta2["depends_on"] = ["Dep-Pkg"]  # Different case

        all_packages = {
            "test-pkg": meta2,
            "dep-pkg": meta1,  # Lowercase
        }

        errors, warnings = validate_package("test-pkg", meta2, all_packages)

        # Should find dep-pkg case-insensitively
        assert not any("unknown" in e.lower() and "depend" in e.lower() for e in errors)

    def test_warns_build_requires_devel_without_depends_on(self):
        """Should warn when -devel build_require is not covered by depends_on."""
        meta = self.get_minimal_package()
        meta["build_requires"] = ["dep-pkg-devel"]
        # No depends_on, or depends_on doesn't include dep-pkg
        meta["depends_on"] = []

        all_packages = {
            "test-pkg": meta,
            "dep-pkg": self.get_minimal_package(),
        }

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should warn about uncovered build_require
        assert any("build_requires" in w.lower() or "covered" in w.lower() for w in warnings)

    def test_warns_build_requires_pkgconfig_without_depends_on(self):
        """Should warn when pkgconfig build_require is not covered by depends_on."""
        meta = self.get_minimal_package()
        meta["build_requires"] = ["pkgconfig(dep-pkg)"]
        meta["depends_on"] = []

        all_packages = {
            "test-pkg": meta,
            "dep-pkg": self.get_minimal_package(),
        }

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("build_requires" in w.lower() or "covered" in w.lower() for w in warnings)

    def test_no_warning_when_build_require_in_depends_on(self):
        """Should not warn when build_require is covered by depends_on."""
        meta = self.get_minimal_package()
        meta["build_requires"] = ["dep-pkg-devel"]
        meta["depends_on"] = ["dep-pkg"]

        all_packages = {
            "test-pkg": meta,
            "dep-pkg": self.get_minimal_package(),
        }

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should not warn about build_requires since depends_on covers it
        assert not any("build_requires" in w.lower() and "covered" in w.lower() for w in warnings)

    def test_warns_unsupported_fedora_version(self):
        """Should warn when fedora override uses unsupported version."""
        meta = self.get_minimal_package()
        meta["fedora"] = {
            "99": {"skip": True},  # 99 is not a supported version
        }

        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should have warning about unsupported version
        assert any("99" in w or "unsupported" in w.lower() for w in warnings)

    def test_errors_on_non_dict_fedora_override(self):
        """Should error when fedora override value is not a dict."""
        meta = self.get_minimal_package()
        meta["fedora"] = {
            "43": "skip",  # Should be a dict, not a string
        }

        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should have error about invalid override format (expects a mapping)
        assert any("fedora" in e.lower() and ("mapping" in e.lower() or "dict" in e.lower()) for e in errors)

    def test_errors_on_unknown_fedora_override_key(self):
        """Should error when fedora override contains unknown keys."""
        meta = self.get_minimal_package()
        meta["fedora"] = {
            "43": {
                "skip": True,
                "invalid_key": "value",  # Unknown key
            }
        }

        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        # Should have error about unknown override key
        assert any("invalid_key" in e or "unknown" in e.lower() for e in errors)


class TestValidateNoDuplicateUrls:
    """Test validate_no_duplicate_urls function.

    Regression coverage for issue #8: Hyprland-git's url lost its ".git"
    suffix, making it identical to stable Hyprland's, which let Hyprland-git's
    auto_update.release_type silently shadow stable Hyprland's in
    update-versions.py and froze it at 0.55.4 for weeks.
    """

    def test_no_duplicates_is_clean(self):
        """Distinct urls produce no warnings or errors."""
        all_packages = {
            "pkg-a": {"url": "https://github.com/org/a"},
            "pkg-b": {"url": "https://github.com/org/b"},
        }

        errors, warnings = validate_no_duplicate_urls(all_packages)

        assert errors == []
        assert warnings == []

    def test_shared_url_warns(self):
        """Two packages sharing a url produce a warning naming both."""
        all_packages = {
            "Hyprland": {"url": "https://github.com/hyprwm/Hyprland"},
            "Hyprland-git": {"url": "https://github.com/hyprwm/Hyprland"},
        }

        errors, warnings = validate_no_duplicate_urls(all_packages)

        assert errors == []
        assert len(warnings) == 1
        assert "Hyprland" in warnings[0]
        assert "Hyprland-git" in warnings[0]

    def test_distinguishing_git_suffix_avoids_warning(self):
        """A .git suffix difference is enough to avoid the collision."""
        all_packages = {
            "Waybar": {"url": "https://github.com/Alexays/Waybar.git"},
            "Waybar-git": {"url": "https://github.com/Alexays/Waybar"},
        }

        errors, warnings = validate_no_duplicate_urls(all_packages)

        assert errors == []
        assert warnings == []

    def test_missing_url_ignored(self):
        """Packages without a url don't spuriously collide with each other."""
        all_packages = {
            "pkg-a": {},
            "pkg-b": {},
        }

        errors, warnings = validate_no_duplicate_urls(all_packages)

        assert errors == []
        assert warnings == []
