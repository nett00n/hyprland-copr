"""Unit tests for scripts/lib/detection.py"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.detection import (
    detect_license,
    detect_build_system,
    extract_cmake_info,
    extract_meson_info,
    extract_version,
    matches_build_system,
    BUILD_SYSTEM_MARKERS,
)


class TestDetectLicense:
    """Test license detection from LICENSE files."""

    def test_detect_mit_from_license(self, tmp_path):
        """Detect MIT license from LICENSE file."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("MIT License\n\nSome text...")
        assert detect_license(repo) == "MIT"

    def test_detect_bsd3_from_license(self, tmp_path):
        """Detect BSD-3-Clause license."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("BSD 3-Clause License")
        assert detect_license(repo) == "BSD-3-Clause"

    def test_detect_from_license_txt(self, tmp_path):
        """LICENSE.txt fallback."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE.txt").write_text("MIT")
        assert detect_license(repo) == "MIT"

    def test_detect_from_copying(self, tmp_path):
        """COPYING file fallback."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "COPYING").write_text("GNU GENERAL PUBLIC LICENSE")
        assert detect_license(repo) == "GPL-3.0-or-later"

    def test_detect_lgpl(self, tmp_path):
        """Detect LGPL license."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("GNU LESSER GENERAL PUBLIC LICENSE")
        assert detect_license(repo) == "LGPL-3.0-or-later"

    def test_no_license_file(self, tmp_path):
        """No license file returns None."""
        repo = tmp_path / "repo"
        repo.mkdir()
        assert detect_license(repo) is None

    def test_unknown_license_content(self, tmp_path):
        """Unknown license content returns None."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("Some custom license text")
        assert detect_license(repo) is None

    def test_case_insensitive_match(self, tmp_path):
        """License matching is case-insensitive."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("mit license")
        assert detect_license(repo) == "MIT"

    def test_empty_license_file(self, tmp_path):
        """Empty license file returns None."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("")
        assert detect_license(repo) is None

    def test_apache_license(self, tmp_path):
        """Detect Apache license."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("Apache License 2.0")
        assert detect_license(repo) == "Apache-2.0"

    def test_isc_license(self, tmp_path):
        """Detect ISC license."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "LICENSE").write_text("ISC License")
        assert detect_license(repo) == "ISC"


class TestDetectBuildSystem:
    """Test build system detection."""

    def test_detect_cmake(self, tmp_path):
        """Detect CMake build system."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "CMakeLists.txt").write_text("")
        assert detect_build_system(repo) == "cmake"

    def test_detect_meson(self, tmp_path):
        """Detect Meson build system."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "meson.build").write_text("")
        assert detect_build_system(repo) == "meson"

    def test_detect_cargo(self, tmp_path):
        """Detect Cargo (Rust) build system."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "Cargo.toml").write_text("")
        assert detect_build_system(repo) == "cargo"

    def test_detect_autotools(self, tmp_path):
        """Detect autotools (configure.ac)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "configure.ac").write_text("")
        assert detect_build_system(repo) == "autotools"

    def test_detect_autotools_from_makefile_in(self, tmp_path):
        """Detect autotools from configure + Makefile.in."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "configure").write_text("")
        (repo / "Makefile.in").write_text("")
        assert detect_build_system(repo) == "autotools"

    def test_detect_make(self, tmp_path):
        """Detect Make build system."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "Makefile").write_text("")
        assert detect_build_system(repo) == "make"

    def test_cmake_priority_over_others(self, tmp_path):
        """CMake detected first even if multiple systems present."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "CMakeLists.txt").write_text("")
        (repo / "Makefile").write_text("")
        assert detect_build_system(repo) == "cmake"

    def test_meson_priority_over_make(self, tmp_path):
        """Meson detected before Make."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "meson.build").write_text("")
        (repo / "Makefile").write_text("")
        assert detect_build_system(repo) == "meson"

    def test_no_build_system(self, tmp_path):
        """Empty directory returns None."""
        repo = tmp_path / "repo"
        repo.mkdir()
        assert detect_build_system(repo) is None


class TestBuildSystemMarkers:
    """BUILD_SYSTEM_MARKERS + matches_build_system() are the single source of truth
    behind both detect_build_system() (below) and
    lib.validation.validate_build_system_drift() (#BUG-0105) -- one table, one
    matcher, no way for the two call sites to independently drift apart."""

    def test_every_marker_is_detected_as_its_own_system(self, tmp_path):
        """Each system's first marker, alone in a repo, round-trips through
        detect_build_system()."""
        for system, markers in BUILD_SYSTEM_MARKERS.items():
            repo = tmp_path / system
            repo.mkdir()
            first = markers[0]
            for name in (first if isinstance(first, tuple) else (first,)):
                (repo / name).write_text("")
            assert detect_build_system(repo) == system

    def test_cmake_and_meson_are_disjoint_marker_sets(self):
        """The hyprland-protocols 0.7.1 case: these two must never share a marker,
        or a meson->cmake switch (or vice versa) would go undetected."""
        assert not set(BUILD_SYSTEM_MARKERS["cmake"]) & set(
            BUILD_SYSTEM_MARKERS["meson"]
        )

    def test_autotools_requires_both_configure_and_makefile_in(self):
        """The compound marker (configure alone is not autotools -- e.g. an
        already-generated tree from another build system entirely) is an
        all-of-tuple, not two independent OR options."""
        assert not matches_build_system("autotools", {"configure"})
        assert not matches_build_system("autotools", {"Makefile.in"})
        assert matches_build_system("autotools", {"configure", "Makefile.in"})
        assert matches_build_system("autotools", {"configure.ac"})

    def test_unknown_system_never_matches(self):
        assert not matches_build_system("FIXME", {"CMakeLists.txt"})


class TestExtractCmakeInfo:
    """Test CMake metadata extraction."""

    def test_extract_description(self):
        """Extract project description."""
        cmake = 'project(foo DESCRIPTION "My project")'
        info = extract_cmake_info(cmake)
        assert info["summary"] == "My project"

    def test_extract_pkg_check_modules(self):
        """Extract pkg_check_modules dependencies (valid pkg names only)."""
        cmake = """
project(foo)
pkg_check_modules(PC_DEPS glib-2.0 libxml-2.0)
"""
        info = extract_cmake_info(cmake)
        assert "pkg_deps" in info
        assert "glib-2.0" in info["pkg_deps"]
        assert "libxml-2.0" in info["pkg_deps"]

    def test_filter_cmake_keywords(self):
        """CMake keywords are not treated as package names."""
        cmake = """
project(foo)
pkg_check_modules(PC REQUIRED glib-2.0)
"""
        info = extract_cmake_info(cmake)
        # REQUIRED should not be in deps
        assert "REQUIRED" not in info.get("pkg_deps", [])
        assert "glib-2.0" in info.get("pkg_deps", [])

    def test_no_description_returns_empty_summary(self):
        """Missing description doesn't add summary key."""
        cmake = "project(foo)"
        info = extract_cmake_info(cmake)
        assert "summary" not in info

    def test_no_pkg_check_modules_returns_empty_deps(self):
        """No pkg_check_modules returns no pkg_deps key."""
        cmake = "project(foo)"
        info = extract_cmake_info(cmake)
        assert "pkg_deps" not in info

    def test_empty_cmake_text(self):
        """Empty text returns empty dict."""
        info = extract_cmake_info("")
        assert info == {}

    def test_multiline_pkg_check_modules(self):
        """pkg_check_modules spanning multiple lines."""
        cmake = """
project(foo)
pkg_check_modules(
  PC_DEPS
  glib-2.0
  gtk+-3.0
)
"""
        info = extract_cmake_info(cmake)
        assert info.get("pkg_deps", [])

    def test_version_spec_stripped_from_dep(self):
        """Version specifications are stripped."""
        cmake = "pkg_check_modules(PC glib-2.0>=2.50)"
        info = extract_cmake_info(cmake)
        assert "glib-2.0" in info.get("pkg_deps", [])


class TestExtractMesonInfo:
    """Test Meson metadata extraction."""

    def test_extract_description(self):
        """Extract project description."""
        meson = "project('foo', description: 'My project')"
        info = extract_meson_info(meson)
        assert info["summary"] == "My project"

    def test_extract_required_dependencies(self):
        """Extract required dependencies."""
        meson = """
project('foo')
dep1 = dependency('glib-2.0')
dep2 = dependency('gtk+-3.0')
"""
        info = extract_meson_info(meson)
        assert "pkg_deps" in info
        assert "glib-2.0" in info["pkg_deps"]
        assert "gtk+-3.0" in info["pkg_deps"]

    def test_skip_optional_dependencies(self):
        """Optional dependencies are skipped."""
        meson = """
project('foo')
dep = dependency('glib-2.0', required: false)
"""
        info = extract_meson_info(meson)
        assert info.get("pkg_deps", []) == []

    def test_skip_threads_dep(self):
        """threads dep is skipped."""
        meson = """
project('foo')
dep = dependency('glib-2.0')
threads = dependency('threads')
"""
        info = extract_meson_info(meson)
        assert "threads" not in info.get("pkg_deps", [])
        assert "glib-2.0" in info.get("pkg_deps", [])

    def test_case_insensitive_description_match(self):
        """description: key is case-insensitive."""
        meson = "project('foo', DESCRIPTION: 'My project')"
        info = extract_meson_info(meson)
        assert info["summary"] == "My project"

    def test_empty_meson_text(self):
        """Empty text returns empty dict."""
        info = extract_meson_info("")
        assert info == {}

    def test_no_duplicates_in_deps(self):
        """Duplicate deps appear once."""
        meson = """
project('foo')
dep = dependency('glib-2.0')
dep2 = dependency('glib-2.0')
"""
        info = extract_meson_info(meson)
        deps = info.get("pkg_deps", [])
        assert deps.count("glib-2.0") == 1


class TestExtractVersion:
    """Test version extraction from VERSION file."""

    def test_extract_version_from_file(self, tmp_path):
        """Extract version from VERSION file."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("1.2.3")
        assert extract_version(repo) == "1.2.3"

    def test_version_with_trailing_newline(self, tmp_path):
        """Trailing newline is stripped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("1.2.3\n")
        assert extract_version(repo) == "1.2.3"

    def test_version_with_leading_whitespace(self, tmp_path):
        """Leading whitespace is stripped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("  1.2.3\n")
        assert extract_version(repo) == "1.2.3"

    def test_no_version_file(self, tmp_path):
        """Missing VERSION file returns None."""
        repo = tmp_path / "repo"
        repo.mkdir()
        assert extract_version(repo) is None

    def test_empty_version_file(self, tmp_path):
        """Empty VERSION file returns empty string."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("")
        assert extract_version(repo) == ""

    def test_complex_version_string(self, tmp_path):
        """Complex version strings are extracted."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("0.54.2^20260327git2c4852e")
        assert extract_version(repo) == "0.54.2^20260327git2c4852e"
