"""Tests for scripts/pkg-log-analysis.py's multi-package CLI.

`make stage-log-analyze` used to spawn one container per package (a shell for
loop in the Makefile). main() now takes every package name in one call, so a
single container analyzes all of them -- a package with no log dir (the
common case) must be reported and skipped, not treated as a failure, while a
package with real issues must still fail the run.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import importlib

pkg_log_analysis = importlib.import_module("pkg-log-analysis")


class TestMain:
    def test_no_packages_is_usage_error(self):
        assert pkg_log_analysis.main([]) == 1

    def test_all_clean_returns_zero(self):
        with patch.object(pkg_log_analysis, "analyze_package", return_value=0) as mock_analyze:
            assert pkg_log_analysis.main(["pkg-a", "pkg-b"]) == 0
        assert mock_analyze.call_args_list == [(("pkg-a",), {}), (("pkg-b",), {})]

    def test_missing_log_dir_is_skipped_not_failed(self, capsys):
        # analyze_package() returns 2 for "no log dir" -- the common case
        # across the full package set -- and that alone must not fail the run.
        with patch.object(pkg_log_analysis, "analyze_package", return_value=2):
            assert pkg_log_analysis.main(["pkg-a"]) == 0
        assert "No logs for pkg-a" in capsys.readouterr().err

    def test_real_issue_fails_even_with_other_clean_packages(self):
        results = {"clean-pkg": 0, "broken-pkg": 1, "no-logs-pkg": 2}
        with patch.object(
            pkg_log_analysis, "analyze_package", side_effect=lambda pkg: results[pkg]
        ):
            assert pkg_log_analysis.main(list(results)) == 1

    def test_every_package_is_analyzed_even_after_a_failure(self):
        """Unlike the old shell `|| exit 1` loop, one package's issues must not
        stop the rest from being analyzed."""
        seen: list[str] = []

        def fake_analyze(pkg: str) -> int:
            seen.append(pkg)
            return 1 if pkg == "broken-pkg" else 0

        with patch.object(pkg_log_analysis, "analyze_package", side_effect=fake_analyze):
            pkg_log_analysis.main(["broken-pkg", "pkg-b", "pkg-c"])

        assert seen == ["broken-pkg", "pkg-b", "pkg-c"]
