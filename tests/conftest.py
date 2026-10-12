"""Shared fixtures for all tests."""

import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db
from tests.git_helpers import git as _git


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Create minimal valid repo structure in tmp_path.

    Returns dict with paths:
    - root: repo root
    - packages_yaml: path to packages.yaml
    - groups_yaml: path to groups.yaml
    """
    # Monkeypatch lib.paths constants
    from lib import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "PACKAGES_YAML", tmp_path / "packages.yaml")
    monkeypatch.setattr(paths, "GROUPS_YAML", tmp_path / "groups.yaml")
    monkeypatch.setattr(paths, "UPSTREAM_DIR", tmp_path / ".cache" / "upstream")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    monkeypatch.setattr(paths, "TEMPLATE_DIR", tmp_path / "templates")
    build_db.close()

    # Create minimal packages.yaml
    (tmp_path / "packages.yaml").write_text("""valid-pkg:
  version: "1.0"
  license: "MIT"
  summary: "Valid package"
  description: "A valid package for testing"
  url: "https://example.com"
  source:
    archives: ["https://example.com/valid-pkg-1.0.tar.gz"]
  build:
    system: "cmake"
""")

    # Create minimal groups.yaml
    (tmp_path / "groups.yaml").write_text("""core:
  packages:
    - valid-pkg
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
def upstream_repo(tmp_path, monkeypatch):
    from lib import paths

    """A real local origin (main branch, tags v1.0.0/v1.1.0) + a redirected cache dir.

    Returns a dict: url (file:// URL of the origin), path, first/second (commit shas).
    """
    origin = tmp_path / "origin" / "acme" / "widget"
    origin.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=origin)
    (origin / "meson.build").write_text("project('widget')\n")
    _git("add", ".", cwd=origin)
    _git("commit", "-qm", "first", cwd=origin)
    _git("tag", "v1.0.0", cwd=origin)
    first = _git("rev-parse", "HEAD", cwd=origin)
    (origin / "meson.build").write_text("project('widget', version: '1.1.0')\n")
    _git("commit", "-qam", "second", cwd=origin)
    _git("tag", "v1.1.0", cwd=origin)
    second = _git("rev-parse", "HEAD", cwd=origin)

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "UPSTREAM_DIR", tmp_path / ".cache" / "upstream")
    return {"url": origin.as_uri(), "path": origin, "first": first, "second": second}
