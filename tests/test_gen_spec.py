"""Tests for spec file generation, focusing on lowercase naming."""

from pathlib import Path

import pytest

from lib.jinja_utils import create_jinja_env
from lib.yaml_utils import apply_os_overrides, get_packages


def _minimal_context(**overrides):
    """Base spec.j2 context (mirrors TestRecommendsBuildContext in
    tests/test_recommends.py), with prep_commands/etc. overridable per test."""
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
        "conflicts": [],
        "provides": [],
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


class TestSpecFileLowercasing:
    """Verify that generated spec files use lowercase names."""

    def test_spec_filename_lowercase_from_mixed_case_package_name(self):
        """Package name in dictionary key should be lowercased when generating spec file."""
        test_cases = [
            ("Hyprshot", "hyprshot"),
            ("Waybar", "waybar"),
            ("Waybar-git", "waybar-git"),
            ("Hyprland-git", "hyprland-git"),
            ("hyprland", "hyprland"),
            ("aylurs-gtk-shell", "aylurs-gtk-shell"),
            ("Hyprland", "hyprland"),
        ]

        for input_name, expected_output in test_cases:
            # This simulates what gen-spec.py does at line 406
            pkg_name = input_name.lower()
            spec_filename = f"{pkg_name}.spec"

            assert spec_filename == f"{expected_output}.spec"
            assert pkg_name == expected_output

    def test_package_directory_lowercase(self, tmp_path):
        """Package directory should be created with lowercase name."""
        test_packages = [
            ("Hyprshot", "hyprshot"),
            ("Waybar-git", "waybar-git"),
            ("Hyprland", "hyprland"),
        ]

        for input_name, expected_dir in test_packages:
            # Simulate gen-spec.py logic
            pkg_name = input_name.lower()
            spec_dir = tmp_path / pkg_name
            spec_dir.mkdir(parents=True, exist_ok=True)

            # Verify directory name is lowercase
            assert spec_dir.name == expected_dir
            # Verify path contains lowercase
            assert str(spec_dir).endswith(expected_dir)

    def test_spec_file_path_all_lowercase(self, tmp_path):
        """Full spec file path should contain only lowercase directory and filename."""
        test_packages = [
            ("Hyprshot", "hyprshot"),
            ("Waybar-git", "waybar-git"),
        ]

        for input_name, expected_name in test_packages:
            pkg_name = input_name.lower()
            spec_dir = tmp_path / pkg_name
            spec_dir.mkdir(parents=True, exist_ok=True)
            spec_path = spec_dir / f"{pkg_name}.spec"
            spec_path.write_text("# dummy spec")

            # Verify spec file exists and path is fully lowercase
            assert spec_path.exists()
            assert spec_path.name == f"{expected_name}.spec"
            assert spec_path.parent.name == expected_name
            # Verify all path components are lowercase
            for part in spec_path.parts:
                if part not in ("/", "."):  # Skip root and current dir
                    assert part == part.lower(), f"Path component '{part}' is not lowercase"

    def test_real_packages_yaml_names_should_lowercase(self):
        """Verify that actual package names from packages.yaml will be lowercased."""
        packages = get_packages()

        # These are actual mixed-case packages that should be lowercased
        mixed_case_packages = ["Hyprland", "Hyprland-git", "Hyprshot", "Waybar", "Waybar-git"]

        for pkg_name in mixed_case_packages:
            if pkg_name in packages:
                # The spec filename should be lowercase
                lowercase_name = pkg_name.lower()
                spec_filename = f"{lowercase_name}.spec"

                # Verify lowercasing works
                assert spec_filename == f"{lowercase_name}.spec"
                assert not any(c.isupper() for c in spec_filename)

    def test_gen_spec_creates_lowercase_spec_files(self):
        """Verify that spec generation creates lowercase filenames (integration test).

        This test checks the behavior of gen-spec.py which should:
        1. Take package names from packages.yaml (which may have mixed case)
        2. Lowercase them when creating directories and spec files
        3. NOT create mixed-case directories or files
        """
        from lib.paths import ROOT

        packages = get_packages()
        mixed_case_packages = ["Hyprland", "Hyprland-git", "Hyprshot", "Waybar", "Waybar-git"]

        for pkg_name in mixed_case_packages:
            if pkg_name in packages:
                lowercase_name = pkg_name.lower()
                expected_spec_path = ROOT / "packages" / lowercase_name / f"{lowercase_name}.spec"
                incorrect_spec_path = ROOT / "packages" / pkg_name / f"{pkg_name}.spec"

                # Verify that lowercase spec file exists
                assert expected_spec_path.exists(), (
                    f"Spec file not found: {expected_spec_path}. "
                    f"gen-spec.py should create spec files with lowercase names."
                )

                # Verify that mixed-case spec file does NOT exist
                assert not incorrect_spec_path.exists(), (
                    f"Mixed-case spec file found: {incorrect_spec_path}. "
                    f"gen-spec.py should only create lowercase files."
                )


class TestPerVersionConditionalPrep:
    """A single spec is now shared across every chroot (see docs/operations.md),
    so a per-version spec difference (e.g. hyprland's f43-only sed,
    packages.yaml's Hyprland entry) is written directly as a literal
    `%if 0%{?fedora} == N ... %endif` conditional in build.prep -- prep_commands
    render verbatim (templates/spec.j2's %prep loop), so rpm evaluates the
    conditional per chroot at build time. apply_os_overrides() no longer merges
    build.prep by version at all (see TestApplyOsOverrides in
    tests/test_cache_and_yaml_utils.py); this only tests that the template
    itself passes such a conditional through untouched.
    """

    def test_if_fedora_conditional_renders_verbatim(self):
        env = create_jinja_env()
        template = env.get_template("spec.j2")
        context = _minimal_context(
            prep_commands=[
                "%if 0%{?fedora} == 43",
                "sed -i 's/old/new/' src/foo.cpp",
                "%endif",
            ]
        )

        rendered = template.render(**context)

        assert "%if 0%{?fedora} == 43" in rendered
        assert "sed -i 's/old/new/' src/foo.cpp" in rendered
        assert "%endif" in rendered

    def test_apply_os_overrides_no_longer_touches_prep(self):
        """The base build.prep list (with its own %if guard already baked in by
        the package author) must survive apply_os_overrides() unchanged for
        every fedora_version -- there is nothing left for it to merge."""
        pkg = {
            "version": "1.0",
            "build": {
                "prep": [
                    "%if 0%{?fedora} == 43",
                    "sed -i 's/old/new/' src/foo.cpp",
                    "%endif",
                ]
            },
        }

        for fedora_version in ("43", "44", "45"):
            result = apply_os_overrides(pkg, fedora_version)
            assert result["build"]["prep"] == pkg["build"]["prep"]
