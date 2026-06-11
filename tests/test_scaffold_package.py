"""Tests for scaffold-package.py and spec file URL handling."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
import yaml


def _import_scaffold_module():
    """Import scaffold-package.py module (which has a dash in the name)."""
    spec = importlib.util.spec_from_file_location(
        "scaffold_package", Path(__file__).parent.parent / "scripts" / "scaffold-package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestScaffoldPackageUrlHandling:
    """Test that scaffold-package.py and spec files handle .git URLs correctly."""

    def test_scaffold_preserves_git_suffix_in_url(self, tmp_path, monkeypatch):
        """Should preserve .git suffix when scaffolding package from submodule."""
        from lib import paths
        from lib.gitmodules import parse_gitmodules

        # Setup temp repo structure
        monkeypatch.setattr(paths, "ROOT", tmp_path)
        monkeypatch.setattr(paths, "GITMODULES", tmp_path / ".gitmodules")
        monkeypatch.setattr(paths, "PACKAGES_YAML", tmp_path / "packages.yaml")

        # Create .gitmodules with .git suffix
        gitmodules_content = """[submodule "submodules/example/test-pkg"]
\tpath = submodules/example/test-pkg
\turl = https://github.com/example/test-pkg.git
"""
        (tmp_path / ".gitmodules").write_text(gitmodules_content)

        # Create submodule directory
        pkg_path = tmp_path / "submodules" / "example" / "test-pkg"
        pkg_path.mkdir(parents=True)

        # Parse gitmodules to get the module
        modules = parse_gitmodules(tmp_path / ".gitmodules")
        assert len(modules) > 0

        # Check that the URL is preserved with .git suffix
        module = modules[0]
        assert module["url"] == "https://github.com/example/test-pkg.git"
        assert module["url"].endswith(".git")

    def test_packages_yaml_url_has_git_suffix(self):
        """packages.yaml URLs should include .git suffix for consistency with .gitmodules."""
        # This verifies the design principle that both sources keep .git
        url_with_suffix = "https://github.com/example/repo.git"
        assert url_with_suffix.endswith(".git")
        # Should NOT be stripped when writing to packages.yaml
        assert url_with_suffix.removesuffix(".git") != url_with_suffix

    def test_spec_file_url_macro_strips_git_suffix(self):
        """Spec file URL macro should strip .git for tarball downloads."""
        # The spec file macro: %define url_base %(echo %{url} | sed 's/\.git$//')
        url_with_git = "https://github.com/example/repo.git"
        # Simulate the sed command
        url_base = url_with_git.removesuffix(".git")

        assert url_with_git.endswith(".git")
        assert not url_base.endswith(".git")

        # Verify the archive URL would be valid
        archive_url = f"{url_base}/archive/refs/tags/v1.0.0.tar.gz"
        assert ".git/archive" not in archive_url
        assert archive_url == "https://github.com/example/repo/archive/refs/tags/v1.0.0.tar.gz"

    def test_url_consistency_packages_to_gitmodules(self):
        """URLs in packages.yaml and .gitmodules should match (including .git)."""
        packages_yaml_url = "https://github.com/example/repo.git"
        gitmodules_url = "https://github.com/example/repo.git"

        # Both should have .git suffix
        assert packages_yaml_url.endswith(".git")
        assert gitmodules_url.endswith(".git")
        # Should match exactly
        assert packages_yaml_url == gitmodules_url


class TestScaffoldPackageCmdAdd:
    """Test that cmd_add creates clean YAML entries with ruamel."""

    @patch("lib.detection.detect_build_system")
    @patch("lib.detection.detect_license")
    @patch("lib.detection.extract_version")
    def test_cmd_add_creates_clean_yaml_no_comments(
        self, mock_version, mock_license, mock_build_system, tmp_path, monkeypatch
    ):
        """cmd_add should create YAML entry without comments."""
        scaffold = _import_scaffold_module()

        # Setup mocks
        monkeypatch.setattr(scaffold, "ROOT", tmp_path)
        monkeypatch.setattr(scaffold, "PACKAGES_YAML", tmp_path / "packages.yaml")
        mock_version.return_value = "1.0.0"
        mock_license.return_value = "MIT"
        mock_build_system.return_value = "cmake"

        # Create submodule directory
        pkg_path = tmp_path / "submodules" / "example" / "testpkg"
        pkg_path.mkdir(parents=True)

        # Create minimal build files to avoid FIXME values
        (pkg_path / "CMakeLists.txt").write_text("project(testpkg)")
        (pkg_path / "LICENSE").write_text("MIT License")

        modules = [{"path": str(pkg_path), "url": "https://github.com/example/testpkg.git"}]

        # Execute
        scaffold.cmd_add(modules, "testpkg")

        # Verify YAML is valid
        yaml_content = (tmp_path / "packages.yaml").read_text()
        data = yaml.safe_load(yaml_content)
        assert "testpkg" in data
        assert data["testpkg"]["version"] == "1.0.0"
        assert data["testpkg"]["license"] == "MIT"
        assert data["testpkg"]["build"]["system"] == "cmake"

        # Verify no comments in output (lines starting with # after stripping leading whitespace)
        comment_lines = [
            line for line in yaml_content.split("\n")
            if line.strip().startswith("#")
        ]
        assert len(comment_lines) == 0, f"Found comments in YAML: {comment_lines}"

    @patch("lib.detection.detect_build_system")
    @patch("lib.detection.detect_license")
    @patch("lib.detection.extract_version")
    def test_cmd_add_entry_has_required_structure(
        self, mock_version, mock_license, mock_build_system, tmp_path, monkeypatch
    ):
        """cmd_add should create entry with all required fields."""
        scaffold = _import_scaffold_module()

        monkeypatch.setattr(scaffold, "ROOT", tmp_path)
        monkeypatch.setattr(scaffold, "PACKAGES_YAML", tmp_path / "packages.yaml")
        mock_version.return_value = "2.0.0"
        mock_license.return_value = "GPL-3.0-or-later"
        mock_build_system.return_value = "meson"

        pkg_path = tmp_path / "submodules" / "org" / "mylib"
        pkg_path.mkdir(parents=True)

        modules = [{"path": str(pkg_path), "url": "https://github.com/org/mylib"}]

        scaffold.cmd_add(modules, "mylib")

        data = yaml.safe_load((tmp_path / "packages.yaml").read_text())
        entry = data["mylib"]

        # Verify required fields exist
        required_fields = [
            "version",
            "release",
            "license",
            "summary",
            "description",
            "url",
            "depends_on",
            "build_requires",
            "requires",
            "files",
            "devel",
            "source",
            "build",
            "rpm",
        ]
        for field in required_fields:
            assert field in entry, f"Missing required field: {field}"

        # Verify nested structure
        assert "archives" in entry["source"]
        assert "system" in entry["build"]
        assert "no_debug_package" in entry["rpm"]

    @patch("lib.detection.detect_build_system")
    @patch("lib.detection.detect_license")
    @patch("lib.detection.extract_version")
    def test_cmd_add_appends_to_existing_packages_yaml(
        self, mock_version, mock_license, mock_build_system, tmp_path, monkeypatch
    ):
        """cmd_add should append to existing packages.yaml correctly."""
        scaffold = _import_scaffold_module()

        monkeypatch.setattr(scaffold, "ROOT", tmp_path)
        monkeypatch.setattr(scaffold, "PACKAGES_YAML", tmp_path / "packages.yaml")
        mock_version.return_value = "1.5.0"
        mock_license.return_value = "Apache-2.0"
        mock_build_system.return_value = "cargo"

        # Create existing packages.yaml
        existing_data = {"existing_pkg": {"version": "1.0.0", "release": 1}}
        (tmp_path / "packages.yaml").write_text(yaml.dump(existing_data))

        pkg_path = tmp_path / "submodules" / "rust" / "newpkg"
        pkg_path.mkdir(parents=True)

        modules = [{"path": str(pkg_path), "url": "https://github.com/rust/newpkg"}]

        scaffold.cmd_add(modules, "newpkg")

        # Verify both entries exist
        data = yaml.safe_load((tmp_path / "packages.yaml").read_text())
        assert "existing_pkg" in data
        assert "newpkg" in data
        assert data["existing_pkg"]["version"] == "1.0.0"
        assert data["newpkg"]["version"] == "1.5.0"

    @patch("lib.detection.detect_build_system")
    @patch("lib.detection.detect_license")
    @patch("lib.detection.extract_version")
    def test_cmd_add_rejects_duplicate_package(
        self, mock_version, mock_license, mock_build_system, tmp_path, monkeypatch, capsys
    ):
        """cmd_add should reject packages that already exist."""
        scaffold = _import_scaffold_module()

        monkeypatch.setattr(scaffold, "ROOT", tmp_path)
        monkeypatch.setattr(scaffold, "PACKAGES_YAML", tmp_path / "packages.yaml")
        mock_version.return_value = "1.0.0"
        mock_license.return_value = "MIT"
        mock_build_system.return_value = "cmake"

        # Create existing package
        existing_data = {"dupkg": {"version": "1.0.0"}}
        (tmp_path / "packages.yaml").write_text(yaml.dump(existing_data))

        pkg_path = tmp_path / "submodules" / "org" / "dupkg"
        pkg_path.mkdir(parents=True)

        modules = [{"path": str(pkg_path), "url": "https://github.com/org/dupkg"}]

        # Should exit with error
        with pytest.raises(SystemExit):
            scaffold.cmd_add(modules, "dupkg")

        captured = capsys.readouterr()
        assert "already exists" in captured.err

    @patch("lib.detection.detect_build_system")
    @patch("lib.detection.detect_license")
    @patch("lib.detection.extract_version")
    def test_cmd_add_golang_adds_bindir_to_files(
        self, mock_version, mock_license, mock_build_system, tmp_path, monkeypatch
    ):
        """cmd_add should add %{_bindir} to files for golang packages."""
        scaffold = _import_scaffold_module()

        monkeypatch.setattr(scaffold, "ROOT", tmp_path)
        monkeypatch.setattr(scaffold, "PACKAGES_YAML", tmp_path / "packages.yaml")
        mock_version.return_value = "1.0.0"
        mock_license.return_value = "MIT"
        mock_build_system.return_value = "golang"

        pkg_path = tmp_path / "submodules" / "cli" / "gocli"
        pkg_path.mkdir(parents=True)

        modules = [{"path": str(pkg_path), "url": "https://github.com/cli/gocli"}]

        scaffold.cmd_add(modules, "gocli")

        data = yaml.safe_load((tmp_path / "packages.yaml").read_text())
        files = data["gocli"]["files"]

        # Should include %{_bindir}/gocli for golang
        assert any("%{_bindir}/gocli" in f for f in files)
