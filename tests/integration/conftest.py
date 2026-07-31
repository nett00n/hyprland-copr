"""Shared fixtures for integration tests."""

import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib import build_db


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Create minimal valid repo structure in tmp_path.

    Returns dict with paths:
    - root: repo root
    - packages_yaml: path to packages.yaml
    - groups_yaml: path to groups.yaml
    - gitmodules: path to .gitmodules
    """
    # Monkeypatch lib.paths constants
    from lib import paths
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "PACKAGES_YAML", tmp_path / "packages.yaml")
    monkeypatch.setattr(paths, "GROUPS_YAML", tmp_path / "groups.yaml")
    monkeypatch.setattr(paths, "GITMODULES", tmp_path / ".gitmodules")
    monkeypatch.setattr(paths, "BUILD_LOG_DIR", tmp_path / "logs" / "build")
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    monkeypatch.setattr(paths, "TEMPLATE_DIR", tmp_path / "templates")
    build_db.close()

    # Create minimal packages.yaml
    (tmp_path / "packages.yaml").write_text("""{
  valid-pkg:
    version: "1.0"
    license: "MIT"
    summary: "Valid package"
    description: "A valid package for testing"
    url: "https://example.com"
    source:
      archives: ["https://example.com/valid-pkg-1.0.tar.gz"]
    build:
      system: "cmake"
}
""")

    # Create minimal groups.yaml
    (tmp_path / "groups.yaml").write_text("""{
  core:
    packages:
      - valid-pkg
}
""")

    # Create minimal .gitmodules
    (tmp_path / ".gitmodules").write_text("""[submodule "valid-pkg"]
	path = submodules/valid-pkg
	url = https://github.com/example/valid-pkg.git
""")

    # Create templates dir
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "spec.j2").write_text("# placeholder spec template\n")

    # Create packages subdir structure
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "valid-pkg").mkdir()

    return {
        "root": tmp_path,
        "packages_yaml": tmp_path / "packages.yaml",
        "groups_yaml": tmp_path / "groups.yaml",
        "gitmodules": tmp_path / ".gitmodules",
    }


@pytest.fixture
def minimal_package():
    """Return a minimal package dict that passes validate_package()."""
    pkg = {
        "version": "1.0",
        "license": "MIT",
        "summary": "Test package",
        "description": "A test package",
        "url": "https://example.com",
        "source": {
            "archives": ["https://example.com/test-1.0.tar.gz"],
        },
        "build": {
            "system": "cmake",
        },
    }
    return pkg


@pytest.fixture
def monkeypatch_cwd(monkeypatch):
    """Helper to change CWD with monkeypatch.chdir()."""
    return monkeypatch
