"""#COPR-0022: tests for lib.log_retention -- the retention policy on
logs/runs/<run_id>/, replacing the old "delete everything at the start of the
next run" behavior.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import log_retention
from lib.log_retention import (
    DEFAULT_RETENTION_RUNS,
    list_run_dirs_newest_first,
    prune_run_logs,
    refresh_latest_link,
    retention_from_env,
)


@pytest.fixture(autouse=True)
def runs_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(log_retention, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    return tmp_path / "logs" / "runs"


def _make_run(runs_dir: Path, run_id: int) -> Path:
    d = runs_dir / str(run_id) / "fedora-44-x86_64" / "pkg"
    d.mkdir(parents=True)
    return runs_dir / str(run_id)


class TestListRunDirsNewestFirst:
    def test_missing_dir_returns_empty(self, runs_log_dir):
        assert list_run_dirs_newest_first() == []

    def test_sorted_newest_first(self, runs_log_dir):
        _make_run(runs_log_dir, 1)
        _make_run(runs_log_dir, 10)
        _make_run(runs_log_dir, 3)

        result = list_run_dirs_newest_first()

        assert [run_id for run_id, _path in result] == [10, 3, 1]

    def test_non_numeric_entries_are_ignored(self, runs_log_dir):
        _make_run(runs_log_dir, 1)
        (runs_log_dir / "latest").symlink_to("1", target_is_directory=True)

        result = list_run_dirs_newest_first()

        assert [run_id for run_id, _path in result] == [1]

    def test_files_under_runs_dir_are_ignored(self, runs_log_dir):
        _make_run(runs_log_dir, 1)
        (runs_log_dir / "README").write_text("not a run")

        result = list_run_dirs_newest_first()

        assert [run_id for run_id, _path in result] == [1]


class TestPruneRunLogs:
    def test_keeps_newest_n(self, runs_log_dir):
        for run_id in range(1, 6):
            _make_run(runs_log_dir, run_id)

        removed = prune_run_logs(keep=2)

        assert sorted(removed) == [1, 2, 3]
        remaining = {run_id for run_id, _path in list_run_dirs_newest_first()}
        assert remaining == {4, 5}

    def test_fewer_runs_than_keep_is_a_noop(self, runs_log_dir):
        _make_run(runs_log_dir, 1)
        _make_run(runs_log_dir, 2)

        removed = prune_run_logs(keep=10)

        assert removed == []
        assert {run_id for run_id, _path in list_run_dirs_newest_first()} == {1, 2}

    def test_missing_runs_dir_is_a_noop(self, runs_log_dir):
        assert prune_run_logs(keep=5) == []

    def test_rejects_non_positive_keep(self, runs_log_dir):
        with pytest.raises(ValueError):
            prune_run_logs(keep=0)

    def test_never_touches_non_runs_log_files(self, tmp_path, monkeypatch):
        """logs/make, logs/.pipeline.lock, logs/build-report.db.last etc. live
        as siblings of logs/runs/, not inside it -- prune_run_logs() must never
        reach outside RUNS_LOG_DIR."""
        logs_dir = tmp_path / "logs"
        runs_dir = logs_dir / "runs"
        monkeypatch.setattr(log_retention, "RUNS_LOG_DIR", runs_dir)
        (logs_dir / "make").mkdir(parents=True)
        (logs_dir / "build-report.db.last").write_text("snapshot")
        for run_id in range(1, 4):
            _make_run(runs_dir, run_id)

        prune_run_logs(keep=1)

        assert (logs_dir / "make").exists()
        assert (logs_dir / "build-report.db.last").exists()


class TestRefreshLatestLink:
    def test_points_at_run_dir(self, runs_log_dir):
        _make_run(runs_log_dir, 5)

        refresh_latest_link(5)

        link = runs_log_dir / "latest"
        assert link.is_symlink()
        assert link.resolve() == (runs_log_dir / "5").resolve()

    def test_replaces_existing_link(self, runs_log_dir):
        _make_run(runs_log_dir, 1)
        _make_run(runs_log_dir, 2)
        refresh_latest_link(1)

        refresh_latest_link(2)

        assert (runs_log_dir / "latest").resolve() == (runs_log_dir / "2").resolve()

    def test_missing_run_dir_is_a_noop(self, runs_log_dir):
        refresh_latest_link(99)  # should not raise
        assert not (runs_log_dir / "latest").exists()


class TestRetentionFromEnv:
    def test_unset_returns_default(self, monkeypatch):
        monkeypatch.delenv("LOG_RETENTION_RUNS", raising=False)
        assert retention_from_env() == DEFAULT_RETENTION_RUNS

    def test_valid_value_is_used(self, monkeypatch):
        monkeypatch.setenv("LOG_RETENTION_RUNS", "3")
        assert retention_from_env() == 3

    def test_non_numeric_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("LOG_RETENTION_RUNS", "not-a-number")
        assert retention_from_env() == DEFAULT_RETENTION_RUNS

    def test_non_positive_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("LOG_RETENTION_RUNS", "0")
        assert retention_from_env() == DEFAULT_RETENTION_RUNS
