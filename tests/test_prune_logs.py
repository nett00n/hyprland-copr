"""#COPR-0022: tests for scripts/prune-logs.py's CLI."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

prune_logs = importlib.import_module("prune-logs")


@pytest.fixture(autouse=True)
def runs_log_dir(tmp_path, monkeypatch):
    runs_dir = tmp_path / "logs" / "runs"
    monkeypatch.setattr(prune_logs, "LOG_DIR", tmp_path / "logs")
    from lib import log_retention

    monkeypatch.setattr(log_retention, "RUNS_LOG_DIR", runs_dir)
    return runs_dir


def _make_run(runs_dir: Path, run_id: int) -> None:
    (runs_dir / str(run_id) / "fedora-44-x86_64" / "pkg").mkdir(parents=True)


class TestMain:
    def test_dry_run_does_not_delete(self, runs_log_dir, capsys):
        for run_id in range(1, 4):
            _make_run(runs_log_dir, run_id)

        exit_code = prune_logs.main(["--keep", "1"])

        assert exit_code == 0
        assert "Dry-run" in capsys.readouterr().out
        assert (runs_log_dir / "1").exists()
        assert (runs_log_dir / "3").exists()

    def test_confirm_deletes(self, runs_log_dir):
        for run_id in range(1, 4):
            _make_run(runs_log_dir, run_id)

        exit_code = prune_logs.main(["--keep", "1", "--confirm"])

        assert exit_code == 0
        assert not (runs_log_dir / "1").exists()
        assert not (runs_log_dir / "2").exists()
        assert (runs_log_dir / "3").exists()

    def test_nothing_to_prune(self, runs_log_dir, capsys):
        _make_run(runs_log_dir, 1)

        exit_code = prune_logs.main(["--keep", "5"])

        assert exit_code == 0
        assert "Nothing to prune" in capsys.readouterr().out

    def test_rejects_non_positive_keep(self, capsys):
        exit_code = prune_logs.main(["--keep", "0"])

        assert exit_code == 1
        assert "must be >= 1" in capsys.readouterr().err

    def test_default_keep_reads_env_var(self, runs_log_dir, monkeypatch):
        monkeypatch.setenv("LOG_RETENTION_RUNS", "1")
        for run_id in range(1, 4):
            _make_run(runs_log_dir, run_id)

        prune_logs.main(["--confirm"])

        assert not (runs_log_dir / "1").exists()
        assert (runs_log_dir / "3").exists()
