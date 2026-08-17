"""Tests for lib.reporting module."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.reporting import (
    badge,
    badge_short,
    event,
    print_summary,
    status,
    verbose_proceed_check,
)


class TestPrintSummary:
    """Test print_summary function."""

    def test_empty_packages_no_crash(self, capsys):
        """print_summary should not crash with empty packages dict."""
        # This previously raised ValueError: max() arg is an empty sequence
        report = {"stages": {}}
        # Should not raise
        print_summary({}, report, copr_repo="")
        captured = capsys.readouterr()
        assert "No packages" in captured.out

    def test_missing_stage_in_report_no_crash(self, capsys):
        """print_summary should handle missing stages in report."""
        report = {"stages": {"spec": {}}}  # missing "mock", "copr", etc.
        packages = {"pkg1": {}}
        # Should not raise KeyError
        print_summary(packages, report, copr_repo="")
        captured = capsys.readouterr()
        # Should have printed something
        assert len(captured.out) > 0

    def test_summary_with_valid_data(self, capsys):
        """print_summary should print valid data."""
        report = {
            "stages": {
                "spec": {"pkg1": {"state": "success"}},
                "vendor": {"pkg1": {"state": "success"}},
                "srpm": {"pkg1": {"state": "success"}},
                "mock": {"pkg1": {"state": "success"}},
                "copr": {"pkg1": {"state": "success", "url": "http://example.com"}},
            }
        }
        packages = {"pkg1": {}}
        print_summary(packages, report, copr_repo="owner/repo")
        captured = capsys.readouterr()
        assert "pkg1" in captured.out or "Summary" in captured.out

    def test_not_vendored_renders_n_a_not_cached(self, capsys):
        """A package with no vendor stage (reason="not-vendored") shows "n/a", not
        "cached" -- the symptom of docs/bugs.md's (now-fixed) BUG-0045 -- and no
        stray "(timestamp)" suffix.
        """
        stages = {
            "vendor": {
                "pkg1": {
                    "state": "skipped",
                    "reason": "not-vendored",
                    "completed_at": "2026-08-18T00:00:00Z",
                }
            },
        }
        packages = {"pkg1": {}}
        print_summary(packages, stages, copr_repo="")
        captured = capsys.readouterr()
        assert "n/a" in captured.out
        assert "cached" not in captured.out
        assert "SKIP" not in captured.out
        assert "2026-08-18" not in captured.out

    def test_cached_reason_still_renders_cached(self, capsys):
        """A genuine cache hit still renders "cached"."""
        stages = {
            "vendor": {"pkg1": {"state": "skipped", "reason": "cached"}},
        }
        packages = {"pkg1": {}}
        print_summary(packages, stages, copr_repo="")
        captured = capsys.readouterr()
        assert "cached" in captured.out
        assert "n/a" not in captured.out

    def test_other_skip_reason_still_renders_skip_with_timestamp(self, capsys):
        """A skip for any other reason keeps the existing SKIP(timestamp) rendering."""
        stages = {
            "vendor": {
                "pkg1": {
                    "state": "skipped",
                    "reason": "config: skip",
                    "completed_at": "2026-08-18T00:00:00Z",
                }
            },
        }
        packages = {"pkg1": {}}
        print_summary(packages, stages, copr_repo="")
        captured = capsys.readouterr()
        assert "SKIP(2026-08-18T00:00:00Z)" in captured.out


class TestEvent:
    """Test the low-level event() line format."""

    def test_line_shape(self, capsys):
        """One tab-separated line: rfc3339 ts, stage=, target=, pkg=, state=."""
        event("mock", "fedora-43-x86_64", "hyprland", "run")
        line = capsys.readouterr().out.strip()
        fields = line.split("\t")
        assert len(fields) == 5
        datetime.fromisoformat(fields[0])  # raises if not a valid RFC3339 timestamp
        assert fields[1] == "stage=mock"
        assert fields[2] == "target=fedora-43-x86_64"
        assert fields[3] == "pkg=hyprland"
        assert fields[4] == "state=RUN"

    def test_extra_fields_appended(self, capsys):
        """Extra kwargs become their own key=value tab fields, in call order."""
        event("mock", "fedora-43-x86_64", "hyprland", "ok", dur="41.2s")
        line = capsys.readouterr().out.strip()
        assert line.endswith("state=OK\tdur=41.2s")

    def test_empty_extra_fields_omitted(self, capsys):
        """A falsy/empty extra field is dropped, not printed as key=."""
        event("mock", "fedora-43-x86_64", "hyprland", "skip", reason="")
        line = capsys.readouterr().out.strip()
        assert "reason=" not in line

    def test_no_color_when_not_a_tty(self, capsys):
        """capsys is never a tty, so no ANSI escapes should leak into captured output."""
        event("mock", "fedora-43-x86_64", "hyprland", "fail")
        line = capsys.readouterr().out
        assert "\033[" not in line

    def test_stage_colorized_on_tty(self, capsys, monkeypatch):
        """Each stage gets its own ANSI color on the stage= value when on a tty."""
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        monkeypatch.delenv("NO_COLOR", raising=False)
        event("mock", "fedora-43-x86_64", "hyprland", "run")
        line = capsys.readouterr().out
        assert "\033[95mmock\033[0m" in line

    def test_different_stages_get_different_colors(self, capsys, monkeypatch):
        """Two different stages must not share the same stage= color."""
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        monkeypatch.delenv("NO_COLOR", raising=False)
        event("mock", "fedora-43-x86_64", "hyprland", "run")
        mock_line = capsys.readouterr().out
        event("spec", "fedora-43-x86_64", "hyprland", "run")
        spec_line = capsys.readouterr().out
        mock_color = mock_line.split("stage=", 1)[1].split("hyprland")[0]
        spec_color = spec_line.split("stage=", 1)[1].split("hyprland")[0]
        assert mock_color != spec_color

    def test_no_stage_color_when_not_a_tty(self, capsys):
        """Stage color must respect the same tty/NO_COLOR gate as state color."""
        event("mock", "fedora-43-x86_64", "hyprland", "run")
        line = capsys.readouterr().out
        assert "\tstage=mock\t" in line


class TestStatus:
    """Test status function."""

    def test_status_ok(self, capsys):
        """Should print OK state."""
        status("spec", "mypackage", "ok", "fedora-43-x86_64")
        captured = capsys.readouterr()
        assert "state=OK" in captured.out
        assert "stage=spec" in captured.out
        assert "pkg=mypackage" in captured.out
        assert "target=fedora-43-x86_64" in captured.out

    def test_status_fail(self, capsys):
        """Should print FAIL state."""
        status("mock", "mypackage", "fail", "fedora-43-x86_64")
        captured = capsys.readouterr()
        assert "state=FAIL" in captured.out
        assert "stage=mock" in captured.out

    def test_status_skip(self, capsys):
        """Should print SKIP state."""
        status("vendor", "mypackage", "skip", "fedora-43-x86_64")
        captured = capsys.readouterr()
        assert "state=SKIP" in captured.out
        assert "stage=vendor" in captured.out

    def test_status_with_detail(self, capsys):
        """Should include detail as a reason= field."""
        status("spec", "pkg", "ok", "fedora-43-x86_64", detail="error message")
        captured = capsys.readouterr()
        assert "reason=error message" in captured.out


class TestVerboseProceedCheck:
    """Test verbose_proceed_check function."""

    def test_skip_on_success(self, capsys):
        """Should return True and print action=skip for success state."""
        result = verbose_proceed_check(
            "spec", "mypackage", "success", "fedora-43-x86_64"
        )
        assert result is True
        captured = capsys.readouterr()
        assert "action=skip" in captured.out
        assert "stage=spec" in captured.out
        assert "pkg=mypackage" in captured.out

    def test_retry_on_failed(self, capsys):
        """Should return False and print action=retry for failed state."""
        result = verbose_proceed_check(
            "mock", "mypackage", "failed", "fedora-43-x86_64"
        )
        assert result is False
        captured = capsys.readouterr()
        assert "action=retry" in captured.out
        assert "prior=failed" in captured.out

    def test_run_on_none(self, capsys):
        """Should return False and print action=run/prior=none for None state."""
        result = verbose_proceed_check("spec", "mypackage", None, "fedora-43-x86_64")
        assert result is False
        captured = capsys.readouterr()
        assert "action=run" in captured.out
        assert "prior=none" in captured.out

    def test_run_on_unknown_state(self, capsys):
        """Should return False and print action=run for unknown state."""
        result = verbose_proceed_check(
            "spec", "mypackage", "unknown", "fedora-43-x86_64"
        )
        assert result is False
        captured = capsys.readouterr()
        assert "action=run" in captured.out


class TestBadge:
    """Test badge function."""

    def test_badge_success(self):
        """Should generate success badge."""
        result = badge("spec", "success")
        assert "spec" in result
        assert "success" in result
        assert "brightgreen" in result
        assert "![" in result
        assert "](http" in result

    def test_badge_failed(self):
        """Should generate failed badge."""
        result = badge("mock", "failed")
        assert "mock" in result
        assert "failed" in result
        assert "red" in result

    def test_badge_skipped(self):
        """Should generate skipped badge."""
        result = badge("vendor", "skipped")
        assert "vendor" in result
        assert "skipped" in result
        assert "lightgrey" in result

    def test_badge_unknown(self):
        """Should generate unknown badge with orange color."""
        result = badge("spec", "unknown")
        assert "spec" in result
        assert "unknown" in result
        assert "orange" in result

    def test_badge_none_state(self):
        """Should handle None state as 'unknown'."""
        result = badge("spec", None)
        assert "unknown" in result
        assert "orange" in result

    def test_badge_with_url(self):
        """Should wrap badge in markdown link when URL provided."""
        result = badge("spec", "success", url="http://example.com")
        assert "[" in result
        assert "http://example.com" in result
        assert result.count("[") == 2  # Outer link and image link

    def test_badge_with_style(self):
        """Should add style parameter to shields.io URL."""
        result = badge("spec", "success", style="flat")
        assert "style=flat" in result

    def test_badge_markdown_format(self):
        """Should be valid markdown."""
        result = badge("spec", "success")
        # Should have markdown image syntax ![alt](url)
        assert "![" in result
        assert "](https://img.shields.io" in result


class TestBadgeShort:
    """Test badge_short function."""

    def test_badge_short_success(self):
        """Should generate short success badge with emoji."""
        result = badge_short("spec", "success")
        assert "spec" in result
        assert "brightgreen" in result
        # Emoji is URL-encoded in the shields.io URL
        assert "✔" in result or "%E2%9C%94" in result

    def test_badge_short_failed(self):
        """Should generate short failed badge with emoji."""
        result = badge_short("mock", "failed")
        assert "mock" in result
        assert "red" in result
        # Emoji is URL-encoded in the shields.io URL
        assert "✘" in result or "%E2%9C%98" in result

    def test_badge_short_skipped(self):
        """Should generate short skipped badge with emoji."""
        result = badge_short("vendor", "skipped")
        assert "vendor" in result
        assert "lightgrey" in result
        # Emoji is URL-encoded in the shields.io URL
        assert "○" in result or "%E2%97%8B" in result

    def test_badge_short_unknown(self):
        """Should generate unknown badge with orange."""
        result = badge_short("spec", "unknown")
        assert "spec" in result
        assert "orange" in result

    def test_badge_short_none_state(self):
        """Should handle None as 'unknown'."""
        result = badge_short("spec", None)
        assert "orange" in result

    def test_badge_short_with_url(self):
        """Should wrap in markdown link when URL provided."""
        result = badge_short("spec", "success", url="http://example.com")
        assert "[" in result
        assert "http://example.com" in result

    def test_badge_short_with_style(self):
        """Should add style parameter."""
        result = badge_short("spec", "success", style="flat")
        assert "style=flat" in result
