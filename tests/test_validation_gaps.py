"""Tests for uncovered branches in validation.py."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib import paths
from lib.source_lock import save_lock
from lib.validation import (
    validate_package,
    validate_no_duplicate_urls,
    validate_submodule_url_resolution,
    validate_field_types,
    validate_vendoring,
    validate_tracker_ids,
    validate_dependency_drift,
    FIELD_TYPES,
    REQUIRED_FIELDS,
    VALID_BUILD_SYSTEMS,
)
from lib.version import RELEASE_TYPES


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

    def test_detects_unknown_release_type(self):
        """BUG-0014: an unrecognized auto_update.release_type must error,
        not silently match no dispatch branch in update-versions.py.
        """
        meta = self.get_minimal_package()
        meta["auto_update"] = {"release_type": "latest-tagg"}
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any(
            "release_type" in e.lower() and "latest-tagg" in e for e in errors
        )

    def test_allows_all_valid_release_types(self):
        """Should accept every type in RELEASE_TYPES, including latest-tag."""
        all_packages = {}

        for release_type in RELEASE_TYPES:
            meta = self.get_minimal_package()
            meta["auto_update"] = {"release_type": release_type}
            all_packages["test-" + release_type] = meta

            errors, warnings = validate_package(
                "test-" + release_type, meta, all_packages
            )
            assert not any("release_type" in e.lower() for e in errors)

    def test_allows_missing_auto_update(self):
        """No auto_update block at all is fine (moving, default resolution)."""
        meta = self.get_minimal_package()
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert not any("release_type" in e.lower() for e in errors)

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

    def test_detects_self_dependency(self):
        """A package depending on itself should be an error (formerly only
        checked by scripts/validate-packages.py, see docs/BUGS.md formerly
        BUG-0012)."""
        meta = self.get_minimal_package()
        meta["depends_on"] = ["test-pkg"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("self-dependency" in e.lower() or "itself" in e.lower() for e in errors)

    def test_detects_self_dependency_case_insensitive(self):
        """Self-dependency detection matches the case-insensitive resolution
        used for every other depends_on entry."""
        meta = self.get_minimal_package()
        meta["depends_on"] = ["Test-Pkg"]
        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any("self-dependency" in e.lower() or "itself" in e.lower() for e in errors)

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

    def test_no_warning_for_digit_suffixed_compat_package(self):
        """A digit-suffixed compat package name (e.g. glaze7) resolves via plain
        removesuffix('-devel') without dropping the trailing digit, so
        'glaze7-devel' + depends_on: [glaze7] must not warn.

        Regression guard for the glaze/glaze7 compat-package pattern
        (docs/packaging.md "Compat packages").
        """
        meta = self.get_minimal_package()
        meta["build_requires"] = ["glaze7-devel"]
        meta["depends_on"] = ["glaze7"]

        all_packages = {
            "Hyprland": meta,
            "glaze7": self.get_minimal_package(),
        }

        errors, warnings = validate_package("Hyprland", meta, all_packages)

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

    @pytest.mark.parametrize("key", ["build", "build_requires", "requires"])
    def test_rejects_merge_style_fedora_override_keys(self, key):
        """`fedora:` only resolves `skip` (lib.yaml_utils.apply_os_overrides) --
        `build`/`build_requires`/`requires` used to be accepted here (silently
        dropped by the build) even though scripts/validate-packages.py already
        rejected them, one of the two divergences behind docs/BUGS.md formerly
        BUG-0012. A per-version difference belongs in build.prep/commands/install
        as a literal `%if 0%{?fedora} == N ... %endif` conditional instead."""
        meta = self.get_minimal_package()
        meta["fedora"] = {"43": {key: ["something"]}}

        all_packages = {"test-pkg": meta}

        errors, warnings = validate_package("test-pkg", meta, all_packages)

        assert any(key in e and "unknown" in e.lower() for e in errors)
        assert any("%if 0%{?fedora}" in e for e in errors)


class TestValidatePackageSourceLock:
    """validate_package() warns (never errors -- must not break a fresh
    checkout) when a package's remote sources have no sources.lock.yaml
    entry yet (see docs/BUGS.md BUG-0025)."""

    def get_minimal_package(self):
        return {
            "version": "1.0",
            "license": "MIT",
            "summary": "Test package",
            "description": "A test package",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/pkg-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }

    @pytest.fixture(autouse=True)
    def lock_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "SOURCES_LOCK", tmp_path / "sources.lock.yaml")

    def test_warns_when_no_lock_entry(self):
        meta = self.get_minimal_package()
        errors, warnings = validate_package("test-pkg", meta, {"test-pkg": meta})

        assert errors == []
        assert any("sources.lock.yaml" in w for w in warnings)
        assert any("refresh-checksums PACKAGE=test-pkg" in w for w in warnings)

    def test_no_warning_when_lock_entry_present(self):
        meta = self.get_minimal_package()
        save_lock({"test-pkg": {"pkg-1.0.tar.gz": {"sha256": "abc", "url": "x"}}})

        errors, warnings = validate_package("test-pkg", meta, {"test-pkg": meta})

        assert errors == []
        assert not any("sources.lock.yaml" in w for w in warnings)

    def test_no_warning_when_archives_missing(self):
        """The 'missing required field' error already covers this case --
        don't pile a second, redundant warning on top of it."""
        meta = self.get_minimal_package()
        meta["source"] = {}

        errors, warnings = validate_package("test-pkg", meta, {"test-pkg": meta})

        assert any("source.archives" in e for e in errors)
        assert not any("sources.lock.yaml" in w for w in warnings)


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


class TestValidateSubmoduleUrlResolution:
    """Test validate_submodule_url_resolution function.

    Regression coverage for docs/BUGS.md BUG-0013: Waybar-git's and
    hyprland-plugins-git's packages.yaml url didn't exactly match their
    .gitmodules submodule's url (one missing a trailing ".git", the other
    with a stray one), so update-versions.py's exact-match `url_to_module`
    lookup silently skipped them every run -- no error, no warning, just
    permanent version drift. This check mirrors that exact lookup.
    """

    def test_matching_url_is_clean(self):
        """A package url that exactly matches a .gitmodules url is fine."""
        all_packages = {"pkg-a": {"url": "https://github.com/org/a"}}
        modules = [{"name": "submodules/org/a", "path": "submodules/org/a",
                    "url": "https://github.com/org/a"}]

        errors, warnings = validate_submodule_url_resolution(all_packages, modules)

        assert errors == []
        assert warnings == []

    def test_missing_git_suffix_warns(self):
        """packages.yaml url missing the .git suffix .gitmodules has."""
        all_packages = {"Waybar-git": {"url": "https://github.com/Alexays/Waybar"}}
        modules = [{"name": "submodules/Alexays/Waybar",
                    "path": "submodules/Alexays/Waybar",
                    "url": "https://github.com/Alexays/Waybar.git"}]

        errors, warnings = validate_submodule_url_resolution(all_packages, modules)

        assert errors == []
        assert len(warnings) == 1
        assert "Waybar-git" in warnings[0]
        assert "https://github.com/Alexays/Waybar" in warnings[0]

    def test_stray_git_suffix_warns(self):
        """packages.yaml url has a .git suffix .gitmodules doesn't."""
        all_packages = {
            "hyprland-plugins-git": {
                "url": "https://github.com/hyprwm/hyprland-plugins.git"
            }
        }
        modules = [{"name": "submodules/hyprwm/hyprland-plugins",
                    "path": "submodules/hyprwm/hyprland-plugins",
                    "url": "https://github.com/hyprwm/hyprland-plugins"}]

        errors, warnings = validate_submodule_url_resolution(all_packages, modules)

        assert errors == []
        assert len(warnings) == 1
        assert "hyprland-plugins-git" in warnings[0]

    def test_missing_url_ignored(self):
        """Packages without a url produce no warning (nothing to resolve)."""
        all_packages = {"pkg-a": {}}
        modules = [{"name": "submodules/org/a", "path": "submodules/org/a",
                    "url": "https://github.com/org/a"}]

        errors, warnings = validate_submodule_url_resolution(all_packages, modules)

        assert errors == []
        assert warnings == []

    def test_no_modules_at_all_warns_for_every_url(self):
        """Empty .gitmodules means no package url can resolve."""
        all_packages = {"pkg-a": {"url": "https://github.com/org/a"}}

        errors, warnings = validate_submodule_url_resolution(all_packages, [])

        assert errors == []
        assert len(warnings) == 1

    def test_multiple_mismatches_each_warn_independently(self):
        """Two independently mismatched packages each produce their own warning."""
        all_packages = {
            "Waybar-git": {"url": "https://github.com/Alexays/Waybar"},
            "hyprland-plugins-git": {
                "url": "https://github.com/hyprwm/hyprland-plugins.git"
            },
            "ok-pkg": {"url": "https://github.com/org/ok"},
        }
        modules = [
            {"name": "submodules/Alexays/Waybar", "path": "submodules/Alexays/Waybar",
             "url": "https://github.com/Alexays/Waybar.git"},
            {"name": "submodules/hyprwm/hyprland-plugins",
             "path": "submodules/hyprwm/hyprland-plugins",
             "url": "https://github.com/hyprwm/hyprland-plugins"},
            {"name": "submodules/org/ok", "path": "submodules/org/ok",
             "url": "https://github.com/org/ok"},
        ]

        errors, warnings = validate_submodule_url_resolution(all_packages, modules)

        assert errors == []
        assert len(warnings) == 2
        assert any("Waybar-git" in w for w in warnings)
        assert any("hyprland-plugins-git" in w for w in warnings)
        assert not any("ok-pkg" in w for w in warnings)


class TestValidateFieldTypes:
    """Test validate_field_types (#BUG-0097): packages.yaml scalar type table."""

    def test_correctly_typed_package_is_clean(self):
        meta = {
            "version": "1.0",
            "release": 3,
            "build": {"system": "cmake", "no_lto": True, "prep": ["echo hi"]},
            "depends_on": ["a", "b"],
            "rpm": {"no_debug_package": False},
        }
        errors, warnings = validate_field_types("pkg", meta)
        assert errors == []
        assert warnings == []

    def test_float_version_is_rejected(self):
        """The original BUG-0097 repro: `version: 1.9` parsed as a YAML float."""
        meta = {"version": 1.9}
        errors, _ = validate_field_types("pkg", meta)
        assert any("version" in e and "float" in e for e in errors)

    def test_bool_release_is_rejected(self):
        """bool is an int subclass in Python -- must be rejected explicitly."""
        meta = {"release": True}
        errors, _ = validate_field_types("pkg", meta)
        assert any("release" in e and "bool" in e for e in errors)

    def test_int_release_is_accepted(self):
        meta = {"release": 4}
        errors, _ = validate_field_types("pkg", meta)
        assert errors == []

    def test_string_where_bool_expected_is_rejected(self):
        meta = {"build": {"no_lto": "true"}}
        errors, _ = validate_field_types("pkg", meta)
        assert any("build.no_lto" in e for e in errors)

    def test_string_where_list_expected_is_rejected(self):
        meta = {"depends_on": "not-a-list"}
        errors, _ = validate_field_types("pkg", meta)
        assert any("depends_on" in e for e in errors)

    def test_missing_field_is_not_checked(self):
        """Absence is REQUIRED_FIELDS' job, not this one's."""
        errors, _ = validate_field_types("pkg", {})
        assert errors == []

    def test_null_field_is_not_checked(self):
        meta = {"version": None}
        errors, _ = validate_field_types("pkg", meta)
        assert errors == []

    def test_nested_dotted_path_is_checked(self):
        meta = {"source": {"commit": {"date": 20240101}}}
        errors, _ = validate_field_types("pkg", meta)
        assert any("source.commit.date" in e for e in errors)

    def test_field_types_table_has_no_fedora_keys(self):
        """fedora: override blocks are validated separately, not by this table."""
        assert not any(k.startswith("fedora") for k in FIELD_TYPES)


class TestValidateVendoring:
    """Test validate_vendoring (#BUG-0089): cross-check the vendoring trigger."""

    def _vendored_meta(self, **overrides):
        meta = {
            "build_requires": ["cargo"],
            "source": {"archives": ["https://example.com/x.tar.gz#/x.tar.gz",
                                     "x-1.0-vendor.tar.gz"]},
            "build": {"prep": []},
        }
        meta.update(overrides)
        return meta

    def test_consistent_vendored_package_is_clean(self):
        errors, warnings = validate_vendoring("x", self._vendored_meta())
        assert errors == []
        assert warnings == []

    def test_non_vendored_package_is_clean(self):
        meta = {
            "build_requires": ["cmake"],
            "source": {"archives": ["https://example.com/x.tar.gz"]},
        }
        errors, warnings = validate_vendoring("x", meta)
        assert errors == []
        assert warnings == []

    def test_trigger_without_archive_is_error(self):
        """golang/cargo in build_requires but no -vendor.tar.gz archive."""
        meta = {
            "build_requires": ["golang"],
            "source": {"archives": ["https://example.com/x.tar.gz"]},
        }
        errors, _ = validate_vendoring("x", meta)
        assert any("no '*-vendor.tar.gz'" in e for e in errors)

    def test_archive_without_trigger_is_error(self):
        """A vendor archive declared with no golang/cargo build_requires."""
        meta = {
            "build_requires": ["cmake"],
            "source": {"archives": ["https://example.com/x.tar.gz",
                                     "x-1.0-vendor.tar.gz"]},
        }
        errors, _ = validate_vendoring("x", meta)
        assert any("never runs" in e for e in errors)

    def test_prep_source_index_within_range_is_clean(self):
        meta = self._vendored_meta(
            build={"prep": ["pushd cli", "tar xf %{SOURCE1}", "popd"]}
        )
        errors, _ = validate_vendoring("x", meta)
        assert errors == []

    def test_prep_source_index_out_of_range_is_error(self):
        """A hand-written prep referencing a SOURCEn beyond the archives list."""
        meta = self._vendored_meta(
            build={"prep": ["tar xf %{SOURCE5}"]}
        )
        errors, _ = validate_vendoring("x", meta)
        assert any("SOURCE5" in e for e in errors)


class TestValidateTrackerIds:
    """Test validate_tracker_ids (#BUG-0073): duplicate/misfiled tracker IDs."""

    def test_clean_files_produce_no_errors(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "BUGS.md").write_text("# Bugs\n\n- #BUG-0001 one\n- #BUG-0002 two\n")
        (docs / "TODO.md").write_text("# Todo\n\n- #TODO-0001 one\n")

        assert validate_tracker_ids(tmp_path) == []

    def test_duplicate_id_within_a_file_is_an_error(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "BUGS.md").write_text(
            "# Bugs\n\n- #BUG-0001 one\n- #BUG-0002 two\n- #BUG-0001 again\n"
        )
        (docs / "TODO.md").write_text("# Todo\n")

        errors = validate_tracker_ids(tmp_path)
        assert len(errors) == 1
        assert "BUG-0001" in errors[0]
        assert "2 times" in errors[0]
        assert "3, 5" in errors[0]  # 1-indexed line numbers of both declarations

    def test_misfiled_prefix_is_an_error(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "BUGS.md").write_text("# Bugs\n\n- #TODO-0001 misfiled\n")
        (docs / "TODO.md").write_text("# Todo\n")

        errors = validate_tracker_ids(tmp_path)
        assert any("wrong prefix" in e for e in errors)

    def test_missing_files_produce_no_errors(self, tmp_path):
        assert validate_tracker_ids(tmp_path) == []

    def test_real_repo_trackers_are_consistent(self):
        """Regression pin: the actual docs/BUGS.md + docs/TODO.md stay clean."""
        assert validate_tracker_ids(paths.ROOT) == []


class TestValidateDependencyDrift:
    """Test validate_dependency_drift (#BUG-0056): offline commit-vs-tag drift."""

    def _gitmodules(self, tmp_path, url, rel_path="submodules/dep"):
        (tmp_path / ".gitmodules").write_text(
            f'[submodule "dep"]\n\tpath = {rel_path}\n\turl = {url}\n'
        )
        (tmp_path / rel_path).mkdir(parents=True)

    def test_no_gitmodules_is_clean(self, tmp_path):
        all_packages = {"a": {"auto_update": {"release_type": "pinned-commit"}}}
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []

    def test_uninitialized_submodule_is_silently_skipped(self, tmp_path):
        """No warning when the dependency's submodule dir doesn't exist."""
        (tmp_path / ".gitmodules").write_text(
            '[submodule "dep"]\n\tpath = submodules/dep\n'
            "\turl = https://example.com/dep\n"
        )
        all_packages = {
            "a": {
                "auto_update": {"release_type": "pinned-commit"},
                "source": {"commit": {"date": "20260901"}},
                "depends_on": ["dep"],
            },
            "dep": {"url": "https://example.com/dep", "version": "1.0"},
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []

    @patch("lib.validation.get_tag_commit")
    def test_newer_commit_than_pinned_dependency_warns(self, mock_get_tag, tmp_path):
        self._gitmodules(tmp_path, "https://example.com/dep")
        mock_get_tag.return_value = ("abc123", "abc123", "20260101", None)

        all_packages = {
            "a": {
                "auto_update": {"release_type": "pinned-commit"},
                "source": {"commit": {"date": "20260901"}},
                "depends_on": ["dep"],
            },
            "dep": {"url": "https://example.com/dep", "version": "1.0"},
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert len(warnings) == 1
        assert "'a'" in warnings[0]
        assert "dep" in warnings[0]

    @patch("lib.validation.get_tag_commit")
    def test_older_commit_than_pinned_dependency_is_clean(self, mock_get_tag, tmp_path):
        self._gitmodules(tmp_path, "https://example.com/dep")
        mock_get_tag.return_value = ("abc123", "abc123", "20260901", None)

        all_packages = {
            "a": {
                "auto_update": {"release_type": "pinned-commit"},
                "source": {"commit": {"date": "20260101"}},
                "depends_on": ["dep"],
            },
            "dep": {"url": "https://example.com/dep", "version": "1.0"},
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []

    @patch("lib.validation.get_tag_commit")
    def test_unresolvable_tag_is_silently_skipped(self, mock_get_tag, tmp_path):
        self._gitmodules(tmp_path, "https://example.com/dep")
        mock_get_tag.return_value = None

        all_packages = {
            "a": {
                "auto_update": {"release_type": "pinned-commit"},
                "source": {"commit": {"date": "20260901"}},
                "depends_on": ["dep"],
            },
            "dep": {"url": "https://example.com/dep", "version": "1.0"},
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []

    def test_non_commit_tracked_package_is_skipped(self, tmp_path):
        """Only latest-commit/pinned-commit packages are checked."""
        all_packages = {
            "a": {
                "auto_update": {"release_type": "latest-tag"},
                "source": {"commit": {"date": "20260901"}},
                "depends_on": ["dep"],
            },
            "dep": {"url": "https://example.com/dep", "version": "1.0"},
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []

    @patch("lib.validation.get_tag_commit")
    def test_commit_tracked_dependency_is_skipped(self, mock_get_tag, tmp_path):
        """Comparing two commit-tracked packages isn't this check's job."""
        self._gitmodules(tmp_path, "https://example.com/dep")

        all_packages = {
            "a": {
                "auto_update": {"release_type": "pinned-commit"},
                "source": {"commit": {"date": "20260901"}},
                "depends_on": ["dep"],
            },
            "dep": {
                "auto_update": {"release_type": "latest-commit"},
                "url": "https://example.com/dep",
                "version": "1.0",
            },
        }
        errors, warnings = validate_dependency_drift(all_packages, tmp_path)
        assert errors == []
        assert warnings == []
        mock_get_tag.assert_not_called()
