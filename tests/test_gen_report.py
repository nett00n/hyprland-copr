"""Tests for gen-report.py script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

# Import gen-report as a module
import importlib
gen_report = importlib.import_module("gen-report")


class TestGenReportArgumentParsing:
    """Test argument parsing for gen-report.py."""

    def test_default_format_is_github(self):
        """Default format should be github."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument(
            "--format",
            choices=["github", "copr", "full-report"],
            default="github",
        )
        args = parser.parse_args([])
        assert args.format == "github"

    def test_format_argument_copr(self):
        """Should accept copr format."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument(
            "--format",
            choices=["github", "copr", "full-report"],
            default="github",
        )
        args = parser.parse_args(["--format", "copr"])
        assert args.format == "copr"

    def test_format_argument_full_report(self):
        """Should accept full-report format."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument(
            "--format",
            choices=["github", "copr", "full-report"],
            default="github",
        )
        args = parser.parse_args(["--format", "full-report"])
        assert args.format == "full-report"

    def test_output_argument_defaults_to_none(self):
        """Output argument should default to None."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument(
            "--output",
            type=str,
            default=None,
        )
        args = parser.parse_args([])
        assert args.output is None

    def test_output_argument_accepts_path(self):
        """Should accept file path for output argument."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument(
            "--output",
            type=str,
            default=None,
        )
        args = parser.parse_args(["--output", "./README.md"])
        assert args.output == "./README.md"

    def test_skip_copr_poll_defaults_to_false(self):
        """Skip copr poll should default to False."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument("--skip-copr-poll", action="store_true")
        args = parser.parse_args([])
        assert args.skip_copr_poll is False

    def test_skip_copr_poll_flag_sets_true(self):
        """Should set skip_copr_poll to True when flag provided."""
        parser = gen_report.argparse.ArgumentParser()
        parser.add_argument("--skip-copr-poll", action="store_true")
        args = parser.parse_args(["--skip-copr-poll"])
        assert args.skip_copr_poll is True


class TestGenReportFormatDuration:
    """Test _format_duration function."""

    def test_duration_under_60_seconds(self):
        """Should format durations under 60 seconds as seconds."""
        result = gen_report._format_duration(100, 145, fallback_at=None)
        assert result == "45s"

    def test_duration_under_60_minutes(self):
        """Should format durations under 60 minutes as minutes and seconds."""
        result = gen_report._format_duration(1000, 1125, fallback_at=None)  # 2m 5s
        assert result == "2m 5s"

    def test_duration_whole_minutes(self):
        """Should format whole minutes without seconds suffix."""
        result = gen_report._format_duration(1000, 1120, fallback_at=None)  # 2m
        assert result == "2m"

    def test_duration_hours(self):
        """Should format durations in hours and minutes."""
        result = gen_report._format_duration(1000, 4665, fallback_at=None)  # 1h 1m 5s
        assert result == "1h 1m"

    def test_duration_whole_hours(self):
        """Should format whole hours without minutes suffix."""
        result = gen_report._format_duration(1000, 8200, fallback_at=None)  # 2h
        assert result == "2h"

    def test_duration_missing_start_time(self):
        """Should return empty string when start time is missing."""
        result = gen_report._format_duration(None, 100, fallback_at=None)
        assert result == ""

    def test_duration_missing_end_time(self):
        """Should return empty string when end time is missing."""
        result = gen_report._format_duration(100, None, fallback_at=None)
        assert result == ""

    def test_duration_with_fallback(self):
        """Should use fallback_at when completed_at is missing."""
        result = gen_report._format_duration(100, None, fallback_at=145)
        assert result == "45s"

    def test_duration_invalid_negative(self):
        """Should return empty string for negative durations."""
        result = gen_report._format_duration(200, 100, fallback_at=None)
        assert result == ""


class TestGenReportFormatDate:
    """Test _format_date function."""

    def test_format_date_valid_timestamp(self):
        """Should format timestamp as UTC date string."""
        # Use a fixed timestamp for reproducibility
        result = gen_report._format_date(1609459200)  # 2021-01-01 00:00:00 UTC
        assert "2021-01-01" in result
        assert "00:00:00 UTC" in result

    def test_format_date_none(self):
        """Should return empty string for None timestamp."""
        result = gen_report._format_date(None)
        assert result == ""

    def test_format_date_zero(self):
        """Should return empty string for zero timestamp."""
        result = gen_report._format_date(0)
        assert result == ""


class TestGenReportCollectPackages:
    """Test collect_packages function."""

    def test_collect_packages_empty_stages(self):
        """Should handle empty stages."""
        stages = {}
        pkg_meta = {}
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert packages == []

    def test_collect_packages_single_package(self):
        """Should collect single package from stages."""
        stages = {
            "validate": {"pkg1": {"state": "success"}},
            "spec": {"pkg1": {"state": "success", "version": "1.0.0"}},
        }
        pkg_meta = {"pkg1": {"summary": "Test package"}}
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert len(packages) == 1
        assert packages[0]["name"] == "pkg1"
        assert packages[0]["summary"] == "Test package"

    def test_collect_packages_multiple_packages(self):
        """Should collect multiple packages in order."""
        stages = {
            "validate": {
                "pkg1": {"state": "success"},
                "pkg2": {"state": "success"},
            }
        }
        pkg_meta = {
            "pkg1": {"summary": "Package 1"},
            "pkg2": {"summary": "Package 2"},
        }
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert len(packages) == 2
        assert packages[0]["name"] == "pkg1"
        assert packages[1]["name"] == "pkg2"

    def test_collect_packages_with_copr_url(self):
        """Should generate COPR URL when build_id is present."""
        stages = {
            "copr": {"pkg1": {"state": "succeeded", "build_id": "12345"}}
        }
        pkg_meta = {}
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert len(packages) == 1
        assert "12345" in packages[0]["copr_url"]

    def test_collect_packages_version_fallback(self):
        """Should use version from first available stage."""
        stages = {
            "spec": {"pkg1": {"state": "success", "version": "1.0.0"}},
            "mock": {"pkg1": {"state": "success"}},
        }
        pkg_meta = {}
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert packages[0]["version"] == "1.0.0"

    def test_collect_packages_version_from_srpm(self):
        """Should fall back to srpm version."""
        stages = {
            "srpm": {"pkg1": {"state": "success", "version": "2.0.0"}},
        }
        pkg_meta = {}
        pkg_badge = {}
        packages = gen_report.collect_packages(stages, pkg_meta, pkg_badge)
        assert packages[0]["version"] == "2.0.0"


class TestGenReportCollectContributors:
    """Test collect_contributors function."""

    def test_collect_contributors_with_git(self, tmp_path):
        """Should collect contributors from git log."""
        with patch.object(gen_report, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|alice@example.com\nBob Builder|bob@example.com"
            mock_git.return_value = mock_result

            contributors = gen_report.collect_contributors(tmp_path)

        assert len(contributors) == 2
        assert contributors[0]["name"] == "Alice Author"
        assert contributors[1]["name"] == "Bob Builder"

    def test_collect_contributors_github_user_detection(self, tmp_path):
        """Should detect GitHub usernames from noreply emails."""
        with patch.object(gen_report, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|12345+alice@users.noreply.github.com"
            mock_git.return_value = mock_result

            contributors = gen_report.collect_contributors(tmp_path)

        assert len(contributors) == 1
        assert contributors[0]["github_user"] == "alice"

    def test_collect_contributors_no_duplicates(self, tmp_path):
        """Should not include duplicate contributor names."""
        with patch.object(gen_report, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Alice Author|alice@example.com\nAlice Author|alice.author@example.com"
            mock_git.return_value = mock_result

            contributors = gen_report.collect_contributors(tmp_path)

        assert len(contributors) == 1
        assert contributors[0]["name"] == "Alice Author"

    def test_collect_contributors_git_failure(self, tmp_path):
        """Should return empty list on git failure."""
        with patch.object(gen_report, "run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_git.return_value = mock_result

            contributors = gen_report.collect_contributors(tmp_path)

        assert contributors == []


class TestGenReportGetLatestBlog:
    """Test get_latest_blog function."""

    def test_get_latest_blog_no_blog_dir(self, tmp_path):
        """Should return empty string when blog directory doesn't exist."""
        result = gen_report.get_latest_blog(tmp_path)
        assert result == ""

    def test_get_latest_blog_empty_dir(self, tmp_path):
        """Should return empty string when blog directory is empty."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        result = gen_report.get_latest_blog(tmp_path)
        assert result == ""

    def test_get_latest_blog_single_file(self, tmp_path):
        """Should return latest blog file content."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        blog_file = blog_dir / "2026-01-01-first.md"
        blog_file.write_text("First blog post")

        result = gen_report.get_latest_blog(tmp_path)
        assert result == "First blog post"

    def test_get_latest_blog_multiple_files(self, tmp_path):
        """Should return latest blog file by name."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "2026-01-01-first.md").write_text("First")
        (blog_dir / "2026-02-01-second.md").write_text("Second")
        (blog_dir / "2026-03-01-latest.md").write_text("Latest")

        result = gen_report.get_latest_blog(tmp_path)
        assert result == "Latest"


class TestGenReportMain:
    """Test main() function integration."""

    def test_main_writes_to_stdout_by_default(self, tmp_path, capsys):
        """Should print to stdout when --output not provided."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--format", "github"]):

            mock_poll.return_value = False
            mock_template = MagicMock()
            mock_template.render.return_value = "Generated output"
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

        captured = capsys.readouterr()
        assert "Generated output" in captured.out

    def test_main_writes_to_file_with_output_arg(self, tmp_path):
        """Should write to file when --output provided."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {}")
        output_file = tmp_path / "README.md"

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--format", "github", "--output", str(output_file)]):

            mock_poll.return_value = False
            mock_template = MagicMock()
            mock_template.render.return_value = "Generated output"
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

        assert output_file.exists()
        assert output_file.read_text() == "Generated output"

    def test_main_exits_when_build_status_missing(self, tmp_path):
        """Should exit with error when build-report.yaml missing."""
        with patch.object(gen_report, "BUILD_STATUS_YAML", tmp_path / "nonexistent.yaml"), \
             patch("sys.argv", ["gen-report.py"]), \
             pytest.raises(SystemExit) as exc_info:
            gen_report.main()

        assert exc_info.value.code == 1

    def test_main_selects_correct_template(self, tmp_path):
        """Should select correct template based on format."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--format", "full-report"]):

            mock_poll.return_value = False
            mock_template = MagicMock()
            mock_template.render.return_value = ""
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should request full-report.md.j2 template
            mock_jinja_env.get_template.assert_called_with("full-report.md.j2")

    def test_main_saves_updated_copr_status(self, tmp_path):
        """Should save build status when COPR status was updated."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "save_build_status") as mock_save, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py"]):

            mock_poll.return_value = True  # Status was updated
            mock_template = MagicMock()
            mock_template.render.return_value = ""
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should have called save_build_status
            assert mock_save.called

    def test_main_polls_copr_by_default(self, tmp_path):
        """Should poll COPR status by default."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {copr: {}}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py"]):

            mock_poll.return_value = False
            mock_template = MagicMock()
            mock_template.render.return_value = ""
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should have called poll_copr_status
            assert mock_poll.called

    def test_main_skips_copr_poll_when_flag_set(self, tmp_path):
        """Should skip COPR polling when --skip-copr-poll is set."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {copr: {}}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--skip-copr-poll"]):

            mock_template = MagicMock()
            mock_template.render.return_value = ""
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should NOT have called poll_copr_status
            assert not mock_poll.called

    def test_main_with_output_and_skip_copr_poll(self, tmp_path):
        """Should write to file and skip COPR polling when both flags set."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {copr: {}}")
        output_file = tmp_path / "report.md"

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--output", str(output_file), "--skip-copr-poll"]):

            mock_template = MagicMock()
            mock_template.render.return_value = "Report content"
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should have written to file
            assert output_file.exists()
            assert output_file.read_text() == "Report content"
            # Should NOT have polled COPR
            assert not mock_poll.called

    def test_main_copr_update_not_saved_when_skipped(self, tmp_path):
        """Should not save build_status when COPR poll is skipped even if status exists."""
        build_status_yaml = tmp_path / "build-report.yaml"
        build_status_yaml.write_text("run: {}\nstages: {copr: {pkg1: {build_id: 123}}}")

        with patch.object(gen_report, "BUILD_STATUS_YAML", build_status_yaml), \
             patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"), \
             patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"), \
             patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"), \
             patch.object(gen_report, "ROOT", tmp_path), \
             patch.object(gen_report, "poll_copr_status") as mock_poll, \
             patch.object(gen_report, "save_build_status") as mock_save, \
             patch.object(gen_report, "create_jinja_env") as mock_env, \
             patch("sys.argv", ["gen-report.py", "--skip-copr-poll"]):

            mock_template = MagicMock()
            mock_template.render.return_value = ""
            mock_jinja_env = MagicMock()
            mock_jinja_env.get_template.return_value = mock_template
            mock_env.return_value = mock_jinja_env

            gen_report.main()

            # Should NOT have called poll_copr_status
            assert not mock_poll.called
            # Should NOT have saved build_status
            assert not mock_save.called
