"""Integration tests for validation pipeline (stage-validate.py)."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib.validation import (
    validate_package,
    validate_group_membership,
    validate_gitmodules,
)
from lib.yaml_utils import load_packages, load_groups_yaml


class TestValidationPipeline:
    """Test validation functions with real package.yaml and groups.yaml files."""

    def test_valid_package_passes_validation(self, fake_repo, minimal_package):
        """Minimal valid package passes validate_package."""
        packages = {"valid-pkg": minimal_package}

        # Monkeypatch to return our packages
        import lib.yaml_utils as yu
        original_load = yu.load_packages

        def mock_load():
            return packages

        import unittest.mock as mock
        with mock.patch.object(yu, "load_packages", mock_load):
            errors, warnings = validate_package("valid-pkg", minimal_package, packages)

        assert errors == []

    def test_missing_required_field_fails(self, fake_repo, minimal_package):
        """Package missing required field fails validation."""
        del minimal_package["description"]
        packages = {"bad-pkg": minimal_package}

        errors, warnings = validate_package("bad-pkg", minimal_package, packages)
        assert any("description" in e for e in errors)

    def test_missing_source_archives_fails(self, fake_repo, minimal_package):
        """Package missing source.archives fails."""
        del minimal_package["source"]["archives"]
        packages = {"bad-pkg": minimal_package}

        errors, warnings = validate_package("bad-pkg", minimal_package, packages)
        assert any("source.archives" in e for e in errors)

    def test_invalid_build_system_fails(self, fake_repo, minimal_package):
        """Package with invalid build system fails."""
        minimal_package["build"]["system"] = "foobar"
        packages = {"bad-pkg": minimal_package}

        errors, warnings = validate_package("bad-pkg", minimal_package, packages)
        assert any("invalid build_system" in e for e in errors)

    def test_package_not_in_group_fails(self, fake_repo, minimal_package, monkeypatch):
        """Package not in groups.yaml fails group membership check."""
        # Create a package not in groups
        packages = {"orphan-pkg": minimal_package}

        # Monkeypatch load_groups_yaml to return empty groups
        import lib.yaml_utils as yu
        monkeypatch.setattr(yu, "load_groups_yaml", lambda: {"core": {"packages": []}})

        errors, warnings = validate_group_membership(packages)
        assert any("orphan-pkg" in e and "not listed in any group" in e for e in errors)

    def test_gitmodules_http_url_fails(self, fake_repo):
        """HTTP URL in .gitmodules fails validation."""
        bad_gitmodules = fake_repo["root"] / ".gitmodules"

        # Write bad .gitmodules with http URL (also missing ignore = dirty,
        # but the http:// check is what this test is pinning)
        bad_gitmodules.write_text("""[submodule "bad-pkg"]
\tpath = submodules/bad-pkg
\turl = http://github.com/example/bad-pkg.git
\tignore = dirty
""")

        # validate_gitmodules reads root_path / ".gitmodules" directly -- no
        # monkeypatch needed (formerly the root_path arg was dead and every
        # caller had to monkeypatch the module-level GITMODULES constant
        # instead, see docs/BUGS.md formerly BUG-0012)
        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert any("not https://" in e for e in errors)

    def test_gitmodules_wrong_path_prefix_fails(self, fake_repo):
        """Wrong path prefix in .gitmodules fails."""
        bad_gitmodules = fake_repo["root"] / ".gitmodules"

        bad_gitmodules.write_text("""[submodule "bad-pkg"]
\tpath = pkgs/bad-pkg
\turl = https://github.com/example/bad-pkg.git
\tignore = dirty
""")

        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert any("does not start with submodules/" in e for e in errors)

    def test_gitmodules_missing_ignore_dirty_fails(self, fake_repo):
        """Submodule missing `ignore = dirty` fails (formerly only checked by
        scripts/validate-packages.py, docs/BUGS.md formerly BUG-0012)."""
        bad_gitmodules = fake_repo["root"] / ".gitmodules"

        bad_gitmodules.write_text("""[submodule "bad-pkg"]
\tpath = submodules/bad-pkg
\turl = https://github.com/example/bad-pkg.git
""")

        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert any("missing 'ignore = dirty'" in e for e in errors)

    def test_gitmodules_wrong_ignore_value_fails(self, fake_repo):
        """Submodule with `ignore = <not dirty>` fails."""
        bad_gitmodules = fake_repo["root"] / ".gitmodules"

        bad_gitmodules.write_text("""[submodule "bad-pkg"]
\tpath = submodules/bad-pkg
\turl = https://github.com/example/bad-pkg.git
\tignore = all
""")

        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert any(
            "ignore=all" in e and "should be 'ignore = dirty'" in e for e in errors
        )

    def test_unknown_depends_on_fails(self, fake_repo, minimal_package):
        """Package with unknown dependency fails."""
        minimal_package["depends_on"] = ["nonexistent-pkg"]
        packages = {"my-pkg": minimal_package}

        errors, warnings = validate_package("my-pkg", minimal_package, packages)
        assert any("not a known package" in e for e in errors)

    def test_valid_depends_on_passes(self, fake_repo, minimal_package):
        """Package with valid dependency passes."""
        pkg_a = minimal_package.copy()
        pkg_b = minimal_package.copy()
        pkg_b["depends_on"] = ["pkg-a"]
        packages = {"pkg-a": pkg_a, "pkg-b": pkg_b}

        errors, warnings = validate_package("pkg-b", pkg_b, packages)
        assert not any("not a known package" in e for e in errors)

    def test_multiple_packages_independent_failures(self, minimal_package):
        """Multiple packages with different failures all fail independently."""
        import copy

        pkg_valid = copy.deepcopy(minimal_package)

        pkg_no_license = copy.deepcopy(minimal_package)
        del pkg_no_license["license"]

        pkg_no_archives = copy.deepcopy(minimal_package)
        del pkg_no_archives["source"]["archives"]

        packages = {
            "valid": pkg_valid,
            "no-license": pkg_no_license,
            "no-archives": pkg_no_archives,
        }

        errors_valid, _ = validate_package("valid", pkg_valid, packages)
        errors_no_lic, _ = validate_package("no-license", pkg_no_license, packages)
        errors_no_arc, _ = validate_package("no-archives", pkg_no_archives, packages)

        assert errors_valid == []
        assert any("license" in e for e in errors_no_lic)
        assert any("source.archives" in e for e in errors_no_arc)

    def test_gitmodules_valid_passes(self, fake_repo):
        """Valid .gitmodules (fake_repo's fixture already sets ignore = dirty)
        passes validation."""
        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert errors == []

    def test_gitmodules_missing_returns_empty(self, fake_repo):
        """Missing .gitmodules returns no errors (allowed)."""
        (fake_repo["root"] / ".gitmodules").unlink()

        errors, warnings = validate_gitmodules(fake_repo["root"])
        assert errors == []

    def test_deprecated_debuginfo_section_fails(self, fake_repo, minimal_package):
        """Package with deprecated debuginfo section fails."""
        minimal_package["debuginfo"] = {"files": []}
        packages = {"bad": minimal_package}

        errors, warnings = validate_package("bad", minimal_package, packages)
        assert any("deprecated 'debuginfo'" in e for e in errors)
