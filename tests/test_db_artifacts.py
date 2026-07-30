"""Tests for scripts/db-artifacts.py: usage report, prune, reset, forget.

reset()/forget() are thin wrappers over lib.build_db (already covered
exhaustively in tests/test_build_db.py's TestResetOrdering/TestForgetPackage);
these tests focus on what's specific to this module: report formatting,
the prune "keep newest per (package, target, kind)" grouping logic, and
that prune never touches log-kind artifacts.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths

db_artifacts = importlib.import_module("scripts.db-artifacts")

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _artifact(tmp_path, name: str, package: str, kind: str, size: int, mtime: float, target: str = TARGET) -> None:
    f = tmp_path / name
    f.write_bytes(b"x" * size)
    import os

    os.utime(f, (mtime, mtime))
    build_db.record_artifact(str(f), "repo", kind, package, target, None)


class TestUsageReport:
    def test_groups_by_package_target_and_kind(self, tmp_path, capsys):
        _artifact(tmp_path, "a.rpm", "a", "rpm", 1000, 1)
        _artifact(tmp_path, "a.log", "a", "mock_log", 500, 1)
        _artifact(tmp_path, "b.rpm", "b", "rpm", 2000, 1)

        db_artifacts.usage_report()

        out = capsys.readouterr().out
        assert "a" in out
        assert "b" in out
        # a's total is 1000 + 500 = 1500 bytes -> "1.5K"
        assert "1.5K" in out
        assert "TOTAL" in out

    def test_flags_rows_whose_file_is_gone(self, tmp_path, capsys):
        f = tmp_path / "gone.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, None)
        f.unlink()

        db_artifacts.usage_report()

        out = capsys.readouterr().out
        assert "1 artifact row(s): file missing on disk" in out

    def test_no_artifacts_prints_message(self, capsys):
        db_artifacts.usage_report()
        out = capsys.readouterr().out
        assert "No artifacts recorded." in out


class TestPrune:
    def test_dry_run_deletes_nothing(self, tmp_path, capsys):
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=1)
        _artifact(tmp_path, "a-2.rpm", "a", "rpm", 100, mtime=2)

        db_artifacts.prune(confirm=False)

        out = capsys.readouterr().out
        assert "would remove" in out
        assert "Re-run with --confirm" in out
        assert (tmp_path / "a-1.rpm").exists()
        assert (tmp_path / "a-2.rpm").exists()
        assert len(build_db.artifacts(package="a")) == 2

    def test_keeps_newest_per_package_target_kind(self, tmp_path):
        old = tmp_path / "a-1.rpm"
        new = tmp_path / "a-2.rpm"
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=1)
        _artifact(tmp_path, "a-2.rpm", "a", "rpm", 100, mtime=2)

        db_artifacts.prune(confirm=True)

        assert not old.exists()
        assert new.exists()
        remaining = build_db.artifacts(package="a", kind="rpm")
        assert len(remaining) == 1
        assert remaining[0]["path"] == str(new)

    def test_different_kinds_pruned_independently(self, tmp_path):
        """Two rpm builds and one srpm build for the same package: each
        (package, target, kind) group is pruned on its own."""
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=1)
        _artifact(tmp_path, "a-2.rpm", "a", "rpm", 100, mtime=2)
        _artifact(tmp_path, "a-1.src.rpm", "a", "srpm", 100, mtime=1)

        db_artifacts.prune(confirm=True)

        assert len(build_db.artifacts(package="a", kind="rpm")) == 1
        assert len(build_db.artifacts(package="a", kind="srpm")) == 1

    def test_never_touches_logs(self, tmp_path):
        """mock_log artifacts are excluded from pruning entirely, even with
        multiple entries for the same package."""
        _artifact(tmp_path, "a-run1.log", "a", "mock_log", 100, mtime=1)
        _artifact(tmp_path, "a-run2.log", "a", "mock_log", 100, mtime=2)

        db_artifacts.prune(confirm=True)

        assert (tmp_path / "a-run1.log").exists()
        assert (tmp_path / "a-run2.log").exists()
        assert len(build_db.artifacts(package="a", kind="mock_log")) == 2

    def test_different_targets_kept_independently(self, tmp_path):
        """Same package, two fedora targets: each target's artifact survives."""
        f43 = tmp_path / "a-fc43.rpm"
        f44 = tmp_path / "a-fc44.rpm"
        _artifact(tmp_path, "a-fc43.rpm", "a", "rpm", 100, mtime=1, target="fedora-43-x86_64")
        _artifact(tmp_path, "a-fc44.rpm", "a", "rpm", 100, mtime=1, target="fedora-44-x86_64")

        db_artifacts.prune(confirm=True)

        assert f43.exists()
        assert f44.exists()

    def test_nothing_to_prune_message(self, tmp_path, capsys):
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=1)

        db_artifacts.prune(confirm=False)

        assert "Nothing to prune." in capsys.readouterr().out


class TestReset:
    def test_preserves_artifacts(self, tmp_path, capsys):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", TARGET, run_id, "success")
        _artifact(tmp_path, "a.rpm", "a", "rpm", 100, mtime=1)

        db_artifacts.reset()

        assert build_db.get_stage("a", "mock", TARGET) is None
        assert len(build_db.artifacts(package="a")) == 1
        assert "artifacts preserved" in capsys.readouterr().out


class TestForget:
    def test_removes_stage_and_artifact_rows(self, tmp_path, capsys):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", TARGET, run_id, "success")
        _artifact(tmp_path, "a.rpm", "a", "rpm", 100, mtime=1)

        db_artifacts.forget("a")

        assert build_db.get_stage("a", "mock", TARGET) is None
        assert build_db.artifacts(package="a") == []
        assert "Forgot a" in capsys.readouterr().out
