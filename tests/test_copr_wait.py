"""Tests for copr-wait.py script (#BUG-0039)."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths

copr_wait = importlib.import_module("copr-wait")

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed_copr(pkg: str, **fields) -> None:
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    state = fields.pop("state", "unknown")
    build_db.set_stage(pkg, "copr", TARGET, run_id, state, **fields)


class TestCoprWaitMain:
    def test_no_pending_builds_skips_poll_entirely(self, monkeypatch, capsys):
        """Nothing to wait for (no copr rows, or all already terminal) ->
        poll_copr_status is never called."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        _seed_copr("pkg1", build_id=1, state="success")

        with patch.object(copr_wait, "poll_copr_status") as mock_poll:
            copr_wait.main()

        mock_poll.assert_not_called()
        assert "0 pending" in capsys.readouterr().out

    def test_pending_build_triggers_bounded_poll(self, monkeypatch):
        """A non-terminal row with a build_id calls poll_copr_status with the
        env-configured deadline/interval."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.setenv("COPR_POLL_TIMEOUT", "600")
        monkeypatch.setenv("COPR_POLL_INTERVAL", "15")
        _seed_copr("pkg1", build_id=123, state="unknown")

        with patch.object(copr_wait, "poll_copr_status") as mock_poll:
            copr_wait.main()

        mock_poll.assert_called_once()
        _, kwargs = mock_poll.call_args
        assert kwargs["deadline_s"] == 600
        assert kwargs["interval_s"] == 15

    def test_default_timeout_and_interval(self, monkeypatch):
        """No COPR_POLL_TIMEOUT/COPR_POLL_INTERVAL set -> falls back to
        1800/30 (docs/operations.md, .env.example)."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        _seed_copr("pkg1", build_id=123, state="unknown")

        with patch.object(copr_wait, "poll_copr_status") as mock_poll:
            copr_wait.main()

        _, kwargs = mock_poll.call_args
        assert kwargs["deadline_s"] == 1800
        assert kwargs["interval_s"] == 30

    def test_row_without_build_id_is_not_pending(self, monkeypatch, capsys):
        """A copr row with no build_id yet must not count as pending."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        _seed_copr("pkg1", state="pending")  # no build_id

        with patch.object(copr_wait, "poll_copr_status") as mock_poll:
            copr_wait.main()

        mock_poll.assert_not_called()

    def test_package_filter_restricts_scope(self, monkeypatch):
        """PACKAGE=pkg1 only waits on pkg1, even though pkg2 is also pending."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        monkeypatch.setenv("PACKAGE", "pkg1")
        _seed_copr("pkg1", build_id=1, state="unknown")
        _seed_copr("pkg2", build_id=2, state="unknown")

        with patch.object(copr_wait, "poll_copr_status") as mock_poll:
            copr_wait.main()

        args, _ = mock_poll.call_args
        assert args[1] == ["pkg1"]

    def test_reports_resolved_and_still_pending_after_poll(self, monkeypatch, capsys):
        """After poll_copr_status runs, prints how many resolved and names
        whatever is still pending."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        _seed_copr("pkg1", build_id=1, state="unknown")
        _seed_copr("pkg2", build_id=2, state="unknown")

        def fake_poll(target, packages, run_id=None, deadline_s=0, interval_s=30):
            # Simulate pkg1 resolving, pkg2 still building.
            build_db.update_state("pkg1", "copr", TARGET, "success")
            return True

        with patch.object(copr_wait, "poll_copr_status", side_effect=fake_poll):
            copr_wait.main()

        out = capsys.readouterr().out
        assert "1 of 2 resolved" in out
        assert "pkg2" in out

    def test_never_exits_nonzero_on_timeout(self, monkeypatch):
        """A build still non-terminal at the deadline is not a failure --
        main() must not raise SystemExit."""
        monkeypatch.setenv("FEDORA_VERSION", "44")
        _seed_copr("pkg1", build_id=123, state="unknown")

        with patch.object(copr_wait, "poll_copr_status", return_value=False):
            copr_wait.main()  # must not raise
