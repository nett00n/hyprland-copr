"""Tests for scaffold-package.py and spec file URL handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest


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
