"""Tests for archive URL processing in spec file generation."""

import pytest
from lib.spec_utils import process_archive_urls


class TestProcessArchiveUrls:
    """Test cases for process_archive_urls function."""

    def test_git_suffix_stripped_from_url_with_git(self):
        """URL with .git suffix should be stripped."""
        out = process_archive_urls(
            ["%{url}/archive/refs/tags/v%{version}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
        )
        assert out == ["https://github.com/Org/Repo/archive/refs/tags/v%{version}.tar.gz"]
        assert ".git/" not in out[0]

    def test_git_suffix_not_present(self):
        """URL without .git should pass through unchanged."""
        out = process_archive_urls(
            ["%{url}/archive/refs/tags/v%{version}.tar.gz"],
            "https://github.com/Org/Repo",
            "mypkg",
        )
        assert out == ["https://github.com/Org/Repo/archive/refs/tags/v%{version}.tar.gz"]

    def test_commit_hash_expanded(self):
        """Commit hash and short commit should be fully expanded."""
        commit = {"full": "abc1234567890def1234567890def1234567890"}
        out = process_archive_urls(
            ["%{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
            commit,
        )
        expected = "https://github.com/Org/Repo/archive/abc1234567890def1234567890def1234567890/mypkg-abc1234.tar.gz"
        assert out == [expected]

    def test_vendor_tarball_name_expanded(self):
        """%{name} in local filenames should be expanded."""
        out = process_archive_urls(
            ["%{name}-%{version}-vendor.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
        )
        assert out == ["mypkg-%{version}-vendor.tar.gz"]

    def test_url_fragment_preserved(self):
        """URL fragments (#/filename) should be preserved."""
        out = process_archive_urls(
            ["%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
        )
        expected = "https://github.com/Org/Repo/archive/refs/tags/v%{version}.tar.gz#/mypkg-%{version}.tar.gz"
        assert out == [expected]

    def test_explicit_url_passthrough(self):
        """Explicit full URLs should pass through unchanged."""
        out = process_archive_urls(
            ["https://example.com/explicit-file.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
        )
        assert out == ["https://example.com/explicit-file.tar.gz"]

    def test_non_string_entry_passthrough(self):
        """Non-string entries should pass through unchanged."""
        out = process_archive_urls(
            [None, 123, "%{url}/archive/v%{version}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
        )
        assert out[0] is None
        assert out[1] == 123
        assert out[2].startswith("https://github.com/Org/Repo")

    def test_missing_commit_full_key(self):
        """Missing 'full' key in commit dict should not crash."""
        commit = {}  # Missing 'full' key
        out = process_archive_urls(
            ["%{url}/archive/%{commit}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
            commit,
        )
        # %{commit} should remain unexpanded since commit_full is empty
        assert "%{commit}" in out[0]

    def test_version_macro_expanded_when_provided(self):
        """RPM macro %{version} should be expanded when version is provided."""
        out = process_archive_urls(
            [
                "%{url}/archive/refs/tags/v%{version}.tar.gz",
                "%{name}-%{version}-vendor.tar.gz",
            ],
            "https://github.com/Org/Repo.git",
            "mypkg",
            version="1.2.3",
        )
        assert "1.2.3" in out[0]
        assert "1.2.3" in out[1]
        assert "%{version}" not in out[0]
        assert "%{version}" not in out[1]

    def test_version_macro_left_when_empty(self):
        """RPM macro %{version} should be left unexpanded when version is empty."""
        out = process_archive_urls(
            ["%{url}/archive/refs/tags/v%{version}.tar.gz"],
            "https://github.com/Org/Repo.git",
            "mypkg",
            version="",
        )
        assert "%{version}" in out[0]

    def test_no_git_in_https_output(self):
        """Regression guard: no .git/ in HTTPS URLs."""
        archives = [
            "%{url}/archive/refs/tags/v%{version}.tar.gz",
            "%{name}-%{version}-vendor.tar.gz",
            "%{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz",
        ]
        commit = {"full": "abc1234567890def1234567890def1234567890"}  # 40-char hash
        out = process_archive_urls(archives, "https://github.com/X/Y.git", "pkg", commit)
        for entry in out:
            if isinstance(entry, str) and entry.startswith("https://"):
                assert ".git/" not in entry, f"Found .git/ in {entry}"

    def test_package_name_lowercased(self):
        """Package name should always be lowercased."""
        out = process_archive_urls(
            ["%{name}"],
            "https://github.com/Org/Repo.git",
            "MyPackage",
        )
        assert out == ["mypackage"]

    def test_url_trailing_slash_stripped(self):
        """Trailing slash in URL should be stripped."""
        out = process_archive_urls(
            ["%{url}/archive/v%{version}.tar.gz"],
            "https://github.com/Org/Repo/",
            "pkg",
        )
        assert "//archive" not in out[0]
        assert out[0].startswith("https://github.com/Org/Repo/archive")
