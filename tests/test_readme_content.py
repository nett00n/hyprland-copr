"""Tests for lib/readme_content.py."""

from unittest.mock import MagicMock, patch

from lib import readme_content


class TestCollectContributors:
    """Test collect_contributors function."""

    def test_collect_contributors_with_git(self, tmp_path):
        """Should collect contributors from git log."""
        with patch.object(readme_content, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|alice@example.com\nBob Builder|bob@example.com"
            mock_git.return_value = mock_result

            contributors = readme_content.collect_contributors(tmp_path)

        assert len(contributors) == 2
        assert contributors[0]["name"] == "Alice Author"
        assert contributors[1]["name"] == "Bob Builder"

    def test_collect_contributors_github_user_detection(self, tmp_path):
        """Should detect GitHub usernames from noreply emails."""
        with patch.object(readme_content, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|12345+alice@users.noreply.github.com"
            mock_git.return_value = mock_result

            contributors = readme_content.collect_contributors(tmp_path)

        assert len(contributors) == 1
        assert contributors[0]["github_user"] == "alice"

    def test_collect_contributors_no_duplicates(self, tmp_path):
        """Should not include duplicate contributor names."""
        with patch.object(readme_content, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|alice@example.com\nAlice Author|alice.author@example.com"
            mock_git.return_value = mock_result

            contributors = readme_content.collect_contributors(tmp_path)

        assert len(contributors) == 1
        assert contributors[0]["name"] == "Alice Author"

    def test_collect_contributors_git_failure(self, tmp_path):
        """Should return empty list on git failure."""
        with patch.object(readme_content, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_git.return_value = mock_result

            contributors = readme_content.collect_contributors(tmp_path)

        assert contributors == []


class TestGetRecentNews:
    """Test get_recent_news function."""

    def test_no_blog_dir(self, tmp_path):
        """Should return empty list when blog/ directory doesn't exist."""
        result = readme_content.get_recent_news(tmp_path)
        assert result == []

    def test_no_news_file(self, tmp_path):
        """Should return empty list when blog/NEWS.md doesn't exist."""
        (tmp_path / "blog").mkdir()
        result = readme_content.get_recent_news(tmp_path)
        assert result == []

    def test_no_sections(self, tmp_path):
        """Should return empty list when NEWS.md has no `## ` headings."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "NEWS.md").write_text("# News\n\nNo dated entries yet.\n")

        result = readme_content.get_recent_news(tmp_path)
        assert result == []

    def test_single_section(self, tmp_path):
        """Should return one entry with parsed date and body."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "NEWS.md").write_text("# News\n\n## 2026-01-01\n\nFirst post\n")

        result = readme_content.get_recent_news(tmp_path)
        assert result == [{"date": "2026-01-01", "body": "First post"}]

    def test_newest_first_order_preserved(self, tmp_path):
        """Should return entries in file order (newest first), not re-sort them."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "NEWS.md").write_text(
            "# News\n\n"
            "## 2026-03-01\n\nLatest\n\n"
            "## 2026-02-01\n\nSecond\n\n"
            "## 2026-01-01\n\nFirst\n"
        )

        result = readme_content.get_recent_news(tmp_path)
        assert [e["date"] for e in result] == ["2026-03-01", "2026-02-01", "2026-01-01"]
        assert [e["body"] for e in result] == ["Latest", "Second", "First"]

    def test_respects_limit(self, tmp_path):
        """Should return at most `limit` entries, dropping the oldest."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "NEWS.md").write_text(
            "# News\n\n"
            "## 2026-03-01\n\nLatest\n\n"
            "## 2026-02-01\n\nSecond\n\n"
            "## 2026-01-01\n\nFirst\n"
        )

        result = readme_content.get_recent_news(tmp_path, limit=2)
        assert [e["date"] for e in result] == ["2026-03-01", "2026-02-01"]

    def test_default_limit_is_eight(self, tmp_path):
        """Should default to 8 entries when limit isn't specified."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        text = "# News\n\n" + "".join(f"## 2026-01-{i:02d}\n\nEntry {i}\n\n" for i in range(1, 11))
        (blog_dir / "NEWS.md").write_text(text)

        result = readme_content.get_recent_news(tmp_path)
        assert len(result) == 8


class TestGetSections:
    """Test get_sections function."""

    def test_defaults_all_true_when_unset(self):
        """Should default every section to True when repo.yaml has no sections key."""
        result = readme_content.get_sections({})
        assert all(result.values())
        assert set(result) == set(readme_content.DEFAULT_SECTIONS)

    def test_partial_override(self):
        """Should honor explicit overrides while defaulting the rest to True."""
        repo = {"documents": {"sections": {"contributors": False, "news": False}}}
        result = readme_content.get_sections(repo)
        assert result["contributors"] is False
        assert result["news"] is False
        assert result["docs"] is True
        assert result["support"] is True

    def test_documents_key_missing(self):
        """Should not error when `documents` itself is absent from repo.yaml."""
        result = readme_content.get_sections({"name": "some repo"})
        assert all(result.values())
