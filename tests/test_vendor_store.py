"""Tests for lib.vendor_store: the content-addressed vendor tarball cache
that replaces "does a file happen to exist in ~/rpmbuild/SOURCES" (see
docs/todo.md TODO-0002/TODO-0006, docs/bugs.md BUG-0023).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib import paths
from lib.vendor_store import find, store


@pytest.fixture(autouse=True)
def vendor_store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "VENDOR_STORE_DIR", tmp_path / "vendor-store")


def _meta(**overrides):
    meta = {
        "version": "1.0.0",
        "build_requires": ["golang"],
        "url": "https://example.com/pkg",
        "source": {"archives": ["https://example.com/pkg-1.0.0.tar.gz"]},
    }
    meta.update(overrides)
    return meta


class TestFind:
    def test_returns_none_on_empty_store(self):
        assert find("pkg", _meta(), {}) is None

    def test_returns_none_when_tarball_missing_but_meta_present(self, tmp_path):
        """A partially-written or pruned-down-to-meta entry is a miss, not a crash."""
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"contents")
        tarball = store("pkg", meta, {}, built)
        tarball.unlink()  # simulate db-artifacts.py --prune reclaiming the tarball
        assert find("pkg", meta, {}) is None

    def test_finds_after_store(self, tmp_path):
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"vendor contents")

        stored_path = store("pkg", meta, {}, built)
        found = find("pkg", meta, {})

        assert found == stored_path
        assert found.read_bytes() == b"vendor contents"

    def test_miss_when_content_changes(self, tmp_path):
        """Changing anything compute_input_hashes covers (e.g. the source URL,
        standing in for BUG-0023's go_subdir/patches cases) must invalidate --
        never silently reuse a stale tarball.
        """
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"vendor contents")
        store("pkg", meta, {}, built)

        changed_meta = _meta(source={"archives": ["https://example.com/pkg-1.0.0-new.tar.gz"]})
        assert find("pkg", changed_meta, {}) is None

    def test_miss_when_meta_json_corrupt(self, tmp_path):
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"vendor contents")
        stored_path = store("pkg", meta, {}, built)
        (stored_path.parent / "meta.json").write_text("not json")

        assert find("pkg", meta, {}) is None


class TestStore:
    def test_writes_tarball_and_meta(self, tmp_path):
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"vendor contents")

        stored_path = store("pkg", meta, {}, built)

        assert stored_path.exists()
        assert stored_path.name == "vendor.tar.gz"
        meta_path = stored_path.parent / "meta.json"
        assert meta_path.exists()

    def test_meta_records_language_and_version(self, tmp_path):
        import json

        meta = _meta(build_requires=["cargo"], version="2.5.0")
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"x")

        stored_path = store("pkg", meta, {}, built)
        recorded = json.loads((stored_path.parent / "meta.json").read_text())

        assert recorded["language"] == "rust"
        assert recorded["version"] == "2.5.0"
        assert recorded["package"] == "pkg"
        assert "hashes" in recorded

    def test_leaves_built_tarball_in_place(self, tmp_path):
        """store() copies, it doesn't move -- the caller still owns its own
        per-target SOURCES_DIR copy.
        """
        meta = _meta()
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"vendor contents")

        store("pkg", meta, {}, built)

        assert built.exists()

    def test_does_not_touch_tool_subprocess_on_unknown_language(self, tmp_path):
        meta = _meta(build_requires=["cmake"])
        built = tmp_path / "built-vendor.tar.gz"
        built.write_bytes(b"x")

        with patch("lib.vendor_store.subprocess.run") as mock_run:
            store("pkg", meta, {}, built)

        mock_run.assert_not_called()
