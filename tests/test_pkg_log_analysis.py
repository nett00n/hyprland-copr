"""Tests for scripts/pkg-log-analysis.py's multi-package CLI.

`make stage-log-analyze` used to spawn one container per package (a shell for
loop in the Makefile). main() now takes every package name in one call, so a
single container analyzes all of them -- a package with no log dir (the
common case) must be reported and skipped, not treated as a failure, while a
package with real issues must still fail the run.

#COPR-0022: log dirs are now resolved via `resolve_log_dirs()` against the
run-scoped `logs/runs/<run_id>/<target>/<pkg>/` layout, and `--output` writes
a durable Markdown summary.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import importlib

from lib import paths as paths_module

pkg_log_analysis = importlib.import_module("pkg-log-analysis")


class TestMain:
    def test_no_packages_is_usage_error(self):
        assert pkg_log_analysis.main([]) == 1

    def test_all_clean_returns_zero(self):
        with patch.object(
            pkg_log_analysis,
            "resolve_log_dirs",
            side_effect=lambda pkg, run_id, target: [Path(f"/fake/{pkg}")],
        ), patch.object(
            pkg_log_analysis, "analyze_package", return_value=(0, [])
        ) as mock_analyze:
            assert pkg_log_analysis.main(["pkg-a", "pkg-b"]) == 0
        assert [c.args[0] for c in mock_analyze.call_args_list] == ["pkg-a", "pkg-b"]

    def test_missing_log_dir_is_skipped_not_failed(self, capsys):
        # resolve_log_dirs() returns [] for "no run has this package" -- the
        # common case across the full package set -- and that alone must not
        # fail the run.
        with patch.object(pkg_log_analysis, "resolve_log_dirs", return_value=[]):
            assert pkg_log_analysis.main(["pkg-a"]) == 0
        assert "No logs for pkg-a" in capsys.readouterr().err

    def test_real_issue_fails_even_with_other_clean_packages(self):
        results = {"clean-pkg": (0, []), "broken-pkg": (1, ["issue"]), "no-logs-pkg": None}

        def fake_resolve(pkg, run_id, target):
            return [] if results[pkg] is None else [Path(f"/fake/{pkg}")]

        def fake_analyze(pkg, log_dir):
            return results[pkg]

        with patch.object(
            pkg_log_analysis, "resolve_log_dirs", side_effect=fake_resolve
        ), patch.object(pkg_log_analysis, "analyze_package", side_effect=fake_analyze):
            assert pkg_log_analysis.main(list(results)) == 1

    def test_every_package_is_analyzed_even_after_a_failure(self):
        """Unlike the old shell `|| exit 1` loop, one package's issues must not
        stop the rest from being analyzed."""
        seen: list[str] = []

        def fake_analyze(pkg: str, log_dir: Path) -> tuple[int, list[str]]:
            seen.append(pkg)
            return (1 if pkg == "broken-pkg" else 0), []

        with patch.object(
            pkg_log_analysis,
            "resolve_log_dirs",
            side_effect=lambda pkg, run_id, target: [Path(f"/fake/{pkg}")],
        ), patch.object(pkg_log_analysis, "analyze_package", side_effect=fake_analyze):
            pkg_log_analysis.main(["broken-pkg", "pkg-b", "pkg-c"])

        assert seen == ["broken-pkg", "pkg-b", "pkg-c"]


class TestResolveLogDirs:
    """#COPR-0022: resolve_log_dirs() against a real logs/runs/ tree."""

    def _make_run(self, runs_dir: Path, run_id: int, target: str, pkg: str) -> Path:
        d = runs_dir / str(run_id) / target / pkg
        d.mkdir(parents=True)
        return d

    def test_no_runs_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
        assert pkg_log_analysis.resolve_log_dirs("pkg", None, None) == []

    def test_picks_newest_run_with_the_package(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        self._make_run(runs_dir, 1, "fedora-44-x86_64", "pkg")
        newest = self._make_run(runs_dir, 3, "fedora-44-x86_64", "pkg")
        self._make_run(runs_dir, 2, "fedora-44-x86_64", "other-pkg")

        result = pkg_log_analysis.resolve_log_dirs("pkg", None, None)

        assert result == [newest]

    def test_matrix_run_returns_every_target(self, tmp_path, monkeypatch):
        """A matrix night logs the same package once per chroot, in the same
        run_id -- all of them should be analyzed, not just one."""
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        x86 = self._make_run(runs_dir, 5, "fedora-44-x86_64", "pkg")
        aarch64 = self._make_run(runs_dir, 5, "fedora-44-aarch64", "pkg")

        result = pkg_log_analysis.resolve_log_dirs("pkg", None, None)

        assert sorted(result) == sorted([x86, aarch64])

    def test_explicit_run_id_and_target_pin_one_dir_even_if_missing(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        self._make_run(runs_dir, 9, "fedora-44-x86_64", "pkg")

        result = pkg_log_analysis.resolve_log_dirs("pkg", 1, "fedora-43-x86_64")

        assert result == [runs_dir / "1" / "fedora-43-x86_64" / "pkg"]
        assert not result[0].exists()

    def test_explicit_run_id_only_narrows_search(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        older = self._make_run(runs_dir, 2, "fedora-44-x86_64", "pkg")
        self._make_run(runs_dir, 4, "fedora-44-x86_64", "pkg")

        result = pkg_log_analysis.resolve_log_dirs("pkg", 2, None)

        assert result == [older]


class TestAnalyzePackage:
    def test_missing_dir_returns_no_logs(self, tmp_path):
        result, lines = pkg_log_analysis.analyze_package("pkg", tmp_path / "nope")
        assert (result, lines) == (2, [])

    def test_clean_dir_returns_zero(self, tmp_path):
        result, lines = pkg_log_analysis.analyze_package("pkg", tmp_path)
        assert (result, lines) == (0, [])

    def test_real_srpm_issue_is_detected(self, tmp_path):
        (tmp_path / "10-srpm.log").write_text(
            "error: No matching package to install: 'golang-x-devel'\n"
        )
        result, lines = pkg_log_analysis.analyze_package("pkg", tmp_path)
        assert result == 1
        assert any("golang-x-devel" in line for line in lines)


class TestOutputMode:
    """#COPR-0022: --output writes a durable Markdown summary."""

    def test_writes_markdown_linking_to_log_dir(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        pkg_dir = runs_dir / "1" / "fedora-44-x86_64" / "broken-pkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "10-srpm.log").write_text("error: No matching package to install: 'x'\n")

        out_file = tmp_path / "summary.md"
        exit_code = pkg_log_analysis.main(["broken-pkg", "--output", str(out_file)])

        assert exit_code == 1
        content = out_file.read_text()
        assert "broken-pkg" in content
        assert str(pkg_dir) in content

    def test_clean_run_still_writes_summary(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        (runs_dir / "1" / "fedora-44-x86_64" / "clean-pkg").mkdir(parents=True)

        out_file = tmp_path / "summary.md"
        exit_code = pkg_log_analysis.main(["clean-pkg", "--output", str(out_file)])

        assert exit_code == 0
        assert "Clean: 1" in out_file.read_text()

    def test_run_id_and_target_flags_are_parsed(self, tmp_path, monkeypatch):
        runs_dir = tmp_path / "logs" / "runs"
        monkeypatch.setattr(pkg_log_analysis, "RUNS_LOG_DIR", runs_dir)
        monkeypatch.setattr(paths_module, "RUNS_LOG_DIR", runs_dir)
        (runs_dir / "2" / "fedora-43-x86_64" / "pkg").mkdir(parents=True)

        exit_code = pkg_log_analysis.main(
            ["pkg", "--run-id", "2", "--target", "fedora-43-x86_64"]
        )

        assert exit_code == 0
