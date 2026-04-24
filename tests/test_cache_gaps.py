"""Tests for uncovered branches in cache.py."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.cache import (
    compute_input_hashes,
    hashes_match,
)


class TestComputeInputHashes:
    """Test compute_input_hashes function."""

    def test_computes_hashes_for_valid_package(self):
        """Should compute hashes for a valid package."""
        meta = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        result = compute_input_hashes("test-pkg", meta, all_packages)
        assert isinstance(result, dict)
        # Should have some hash keys
        assert len(result) > 0

    def test_computes_hashes_with_no_dependencies(self):
        """Should compute hashes when package has no dependencies."""
        meta = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        result = compute_input_hashes("test-pkg", meta, all_packages)
        assert isinstance(result, dict)

    def test_computes_consistent_hashes(self):
        """Should compute consistent hashes for same input."""
        meta = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        hash1 = compute_input_hashes("test-pkg", meta, all_packages)
        hash2 = compute_input_hashes("test-pkg", meta, all_packages)

        assert hash1 == hash2


class TestHashesMatch:
    """Test hashes_match function."""

    def test_matches_identical_hashes(self):
        """Should return True for identical hashes."""
        stored_entry = {
            "hashes": {
                "config": "abc123",
                "version": "def456",
            }
        }
        new = {
            "config": "abc123",
            "version": "def456",
        }

        result = hashes_match(stored_entry, new)
        assert result is True

    def test_detects_mismatched_hashes(self):
        """Should return False for different hashes."""
        stored_entry = {
            "hashes": {
                "config": "abc123",
                "version": "def456",
            }
        }
        new = {
            "config": "different",
            "version": "def456",
        }

        result = hashes_match(stored_entry, new)
        assert result is False

    def test_returns_false_when_no_stored_hashes(self):
        """Should return False when stored entry has no hashes."""
        stored_entry = {
            "config": "abc123",
        }
        new = {
            "config": "abc123",
            "version": "def456",
        }

        result = hashes_match(stored_entry, new)
        assert result is False

    def test_returns_false_when_stored_hashes_empty(self):
        """Should return False when stored hashes is empty."""
        stored_entry = {
            "hashes": {}
        }
        new = {
            "config": "abc123",
        }

        result = hashes_match(stored_entry, new)
        assert result is False


class TestContentHash:
    """Test _content_hash function (excludes release field)."""

    def test_release_excluded_int_differs(self):
        """_content_hash excludes release → same hash despite different release values."""
        from lib.cache import _content_hash

        pkg1 = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "Test",
        }
        pkg2 = {
            "version": "1.0",
            "release": 2,
            "license": "GPLv3",
            "summary": "Test",
        }
        assert _content_hash(pkg1) == _content_hash(pkg2)

    def test_release_string_excluded(self):
        """_content_hash excludes release even when string."""
        from lib.cache import _content_hash

        pkg1 = {
            "version": "1.0",
            "release": "%autorelease",
            "license": "GPLv3",
            "summary": "Test",
        }
        pkg2 = {
            "version": "1.0",
            "release": 99,
            "license": "GPLv3",
            "summary": "Test",
        }
        assert _content_hash(pkg1) == _content_hash(pkg2)

    def test_version_change_differs(self):
        """_content_hash differs when version changes."""
        from lib.cache import _content_hash

        pkg1 = {"version": "1.0", "release": 1, "license": "GPLv3"}
        pkg2 = {"version": "2.0", "release": 1, "license": "GPLv3"}
        assert _content_hash(pkg1) != _content_hash(pkg2)

    def test_missing_release_field(self):
        """_content_hash same whether release is missing or present."""
        from lib.cache import _content_hash

        pkg1 = {"version": "1.0", "license": "GPLv3", "summary": "Test"}
        pkg2 = {"version": "1.0", "license": "GPLv3", "summary": "Test", "release": 42}
        assert _content_hash(pkg1) == _content_hash(pkg2)

    def test_deterministic(self):
        """_content_hash is deterministic."""
        from lib.cache import _content_hash

        pkg = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "release": 5,
        }
        hash1 = _content_hash(pkg)
        hash2 = _content_hash(pkg)
        assert hash1 == hash2


class TestComputeInputHashesNewFields:
    """Test new fields in compute_input_hashes: content, package_version."""

    def test_includes_content_key(self):
        """compute_input_hashes returns content key."""
        meta = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        result = compute_input_hashes("test-pkg", meta, all_packages)
        assert "content" in result

    def test_includes_package_version_key(self):
        """compute_input_hashes returns package_version key."""
        meta = {
            "version": "1.0",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        result = compute_input_hashes("test-pkg", meta, all_packages)
        assert "package_version" in result

    def test_content_stable_across_release_values(self):
        """content hash is same regardless of release field."""
        meta1 = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        meta2 = {
            "version": "1.0",
            "release": 5,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-1.0.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta1}

        hash1 = compute_input_hashes("test-pkg", meta1, all_packages)
        hash2 = compute_input_hashes("test-pkg", meta2, all_packages)
        assert hash1["content"] == hash2["content"]

    def test_package_version_matches_meta(self):
        """package_version field matches meta version."""
        meta = {
            "version": "2.5.3",
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
            "source": {"archives": ["https://example.com/test-2.5.3.tar.gz"]},
            "build": {"system": "cmake"},
        }
        all_packages = {"test-pkg": meta}

        result = compute_input_hashes("test-pkg", meta, all_packages)
        assert result["package_version"] == "2.5.3"
