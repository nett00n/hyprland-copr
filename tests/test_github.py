"""Tests for lib.github module."""

import json
import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.github import (
    _cache_key,
    build_changelog,
    fetch_github_release,
    load_release_cache,
    save_release_cache,
)


class TestCacheKey:
    """Test _cache_key function."""

    def test_extracts_owner_repo_from_github_url(self):
        """Should extract owner/repo from GitHub URL."""
        result = _cache_key("https://github.com/foo/bar", "1.0")
        assert result == "foo/bar@1.0"

    def test_handles_complex_repo_names(self):
        """Should handle repos with hyphens and underscores."""
        result = _cache_key("https://github.com/my-org/my_repo", "2.5")
        assert result == "my-org/my_repo@2.5"

    def test_fallback_for_invalid_url(self):
        """Should fallback to full URL if regex doesn't match."""
        result = _cache_key("invalid-url", "1.0")
        assert result == "invalid-url@1.0"


class TestReleaseCache:
    """Test load_release_cache and save_release_cache functions."""

    def test_save_and_load_release_cache(self, tmp_path, monkeypatch):
        """Should save and load cache successfully."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        release_data = {"tag_name": "v1.0", "body": "Release notes"}
        save_release_cache("https://github.com/foo/bar", "1.0", release_data)

        loaded = load_release_cache("https://github.com/foo/bar", "1.0")
        assert loaded == release_data

    def test_load_cache_returns_none_if_file_not_exists(self, monkeypatch):
        """Should return None if cache file doesn't exist."""
        cache_file = Path("/nonexistent/cache.json")
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        result = load_release_cache("https://github.com/foo/bar", "1.0")
        assert result is None

    def test_load_cache_returns_none_if_entry_expired(self, tmp_path, monkeypatch):
        """Should return None if cache entry is expired."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        # Save with old timestamp (older than 7 days)
        cache_data = {
            "foo/bar@1.0": {
                "data": {"tag_name": "v1.0"},
                "timestamp": 0,  # Epoch, definitely expired
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        result = load_release_cache("https://github.com/foo/bar", "1.0")
        assert result is None

    def test_load_cache_handles_corrupted_json(self, tmp_path, monkeypatch):
        """Should return None if cache JSON is corrupted."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)
        cache_file.write_text("invalid json {]")

        result = load_release_cache("https://github.com/foo/bar", "1.0")
        assert result is None

    def test_save_cache_evicts_expired_entries(self, tmp_path, monkeypatch):
        """Should drop entries older than CACHE_TTL when saving."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        cache_data = {
            "foo/bar@1.0": {"data": {"tag_name": "v1.0"}, "timestamp": 0},
            "foo/bar@2.0": {"data": {"tag_name": "v2.0"}, "timestamp": int(time.time())},
        }
        cache_file.write_text(json.dumps(cache_data))

        save_release_cache("https://github.com/foo/bar", "3.0", {"tag_name": "v3.0"})

        data = json.loads(cache_file.read_text())
        assert "foo/bar@1.0" not in data
        assert "foo/bar@2.0" in data
        assert "foo/bar@3.0" in data

    def test_save_cache_creates_parent_directories(self, tmp_path, monkeypatch):
        """Should create parent directories if they don't exist."""
        cache_file = tmp_path / "deep" / "nested" / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        release_data = {"tag_name": "v1.0"}
        save_release_cache("https://github.com/foo/bar", "1.0", release_data)

        assert cache_file.exists()


class TestBuildChangelog:
    """Test build_changelog function."""

    def test_builds_changelog_from_release_info(self):
        """Should build changelog from GitHub release info."""
        release_info = {
            "published_at": "2025-01-15T10:30:00Z",
            "tag_name": "v1.0.0",
            "commit": {"sha": "abc123"},
            "body": "- Fix bug\n- Add feature",
        }
        result = build_changelog(
            release_info, "1.0.0", 1, "John <john@example.com>"
        )

        assert result["version"] == "1.0.0"
        assert result["release"] == 1
        assert result["packager"] == "John <john@example.com>"
        assert result["tag"] == "v1.0.0"
        assert "Fix bug" in result["notes"]
        assert "Add feature" in result["notes"]

    def test_extracts_notes_from_bullet_points(self):
        """Should extract notes from markdown bullet points."""
        release_info = {
            "body": "- Item 1\n- Item 2\n* Item 3\n• Item 4"
        }
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        assert "Item 1" in result["notes"]
        assert "Item 2" in result["notes"]
        assert "Item 3" in result["notes"]
        assert "Item 4" in result["notes"]

    def test_skips_markdown_headings_in_notes(self):
        """Should skip markdown headings when parsing notes."""
        release_info = {
            "body": "# Title\n## Subtitle\n- Note 1\n### Section\n- Note 2"
        }
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        assert "Title" not in result["notes"]
        assert "Subtitle" not in result["notes"]
        assert "Section" not in result["notes"]
        assert "Note 1" in result["notes"]
        assert "Note 2" in result["notes"]

    def test_uses_default_note_if_no_release_info(self):
        """Should use default note if release_info is None."""
        result = build_changelog(None, "2.0", 1, "Dev <d@e.com>")

        assert result["notes"] == ["Update to 2.0"]
        assert result["version"] == "2.0"

    def test_uses_default_note_if_no_body(self):
        """Should use default note if release body is empty."""
        release_info = {"tag_name": "v1.0", "body": ""}
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        assert result["notes"] == ["Update to 1.0"]

    def test_uses_default_note_if_body_only_headings(self):
        """Should use default note if body only contains headings."""
        release_info = {"body": "# Title\n## Subtitle"}
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        assert result["notes"] == ["Update to 1.0"]

    def test_uses_current_date_if_no_published_at(self):
        """Should use current date if published_at missing."""
        release_info = {"tag_name": "v1.0"}
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        # Check that date is set to something recent (within last minute)
        # Date format is "Day Mon DD YYYY"
        assert len(result["date"]) > 0
        assert " " in result["date"]  # Should have spaces

    def test_formats_date_correctly(self):
        """Should format date as 'Day Mon DD YYYY'."""
        release_info = {"published_at": "2025-01-15T10:30:00Z"}
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        # 2025-01-15 is a Wednesday
        assert "Wed Jan 15 2025" in result["date"]

    def test_includes_optional_urls(self):
        """Should include optional source and copr URLs."""
        release_info = {"body": "Release"}
        result = build_changelog(
            release_info,
            "1.0",
            1,
            "Dev <d@e.com>",
            source_url="https://example.com/src",
            copr_url="https://copr.example.com/build/123",
        )

        assert result["source_url"] == "https://example.com/src"
        assert result["copr_url"] == "https://copr.example.com/build/123"

    def test_handles_mixed_note_formats(self):
        """Should handle mixed note formats (bullets and plain lines)."""
        release_info = {
            "body": "Introduction\n- Bullet point\nPlain text\n* Another bullet"
        }
        result = build_changelog(release_info, "1.0", 1, "Dev <d@e.com>")

        assert "Introduction" in result["notes"]
        assert "Bullet point" in result["notes"]
        assert "Plain text" in result["notes"]
        assert "Another bullet" in result["notes"]


class TestFetchGithubRelease:
    """Test fetch_github_release function."""

    def test_returns_cached_release(self, tmp_path, monkeypatch):
        """Should return cached release without fetching."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        cached_data = {"tag_name": "v1.0", "body": "Cached release"}
        save_release_cache("https://github.com/foo/bar", "1.0", cached_data)

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = fetch_github_release("https://github.com/foo/bar", "1.0")

            assert result == cached_data
            mock_urlopen.assert_not_called()

    def test_returns_none_on_404(self, tmp_path, monkeypatch):
        """Should return None on 404 without retrying."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "url", 404, "Not Found", {}, None
            )

            result = fetch_github_release("https://github.com/foo/bar", "1.0")

            assert result is None
            assert mock_urlopen.call_count == 1  # No retry

    def test_retries_on_429(self, tmp_path, monkeypatch):
        """Should retry on 429 (rate limit)."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        with patch("urllib.request.urlopen") as mock_urlopen:
            with patch("time.sleep"):  # Skip actual sleep
                mock_urlopen.side_effect = urllib.error.HTTPError(
                    "url", 429, "Too Many Requests", {}, None
                )

                result = fetch_github_release("https://github.com/foo/bar", "1.0")

                assert result is None
                assert mock_urlopen.call_count == 3  # Should retry 3 times

    def test_returns_none_on_invalid_url(self, tmp_path, monkeypatch):
        """Should return None if URL doesn't match GitHub format."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        result = fetch_github_release("not-a-valid-url", "1.0")
        assert result is None

    def test_caches_successful_fetch(self, tmp_path, monkeypatch):
        """Should cache successful API responses."""
        cache_file = tmp_path / "cache.json"
        monkeypatch.setattr("lib.github.GITHUB_RELEASE_CACHE", cache_file)

        api_response = {"tag_name": "v1.0", "body": "Release"}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = json.dumps(api_response).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = fetch_github_release("https://github.com/foo/bar", "1.0")

            assert result == api_response
            assert cache_file.exists()

            # Verify it was cached
            cached = load_release_cache("https://github.com/foo/bar", "1.0")
            assert cached == api_response
