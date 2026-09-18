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


def _artifact(
    tmp_path,
    name: str,
    package: str,
    kind: str,
    size: int,
    mtime: float,
    target: str = TARGET,
    version: str | None = None,
) -> None:
    f = tmp_path / name
    f.write_bytes(b"x" * size)
    import os

    os.utime(f, (mtime, mtime))
    build_db.record_artifact(str(f), "repo", kind, package, target, version)


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

    def test_verify_false_never_hashes(self, tmp_path, capsys):
        """#BUG-0061: without --verify, corruption is not reported at all."""
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, None)
        f.write_bytes(b"corrupted!")  # same size, different content

        db_artifacts.usage_report(verify=False)

        out = capsys.readouterr().out
        assert "sha256 mismatch" not in out

    def test_verify_flags_corrupted_artifact(self, tmp_path, capsys):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, None)
        f.write_bytes(b"corrupte!!")  # same size -> record_artifact's guard wouldn't rehash

        db_artifacts.usage_report(verify=True)

        out = capsys.readouterr().out
        assert "1 artifact(s): sha256 mismatch (corrupted on disk):" in out
        assert str(f) in out

    def test_verify_reports_unverifiable_when_no_sha256(self, tmp_path, capsys):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, None)
        conn = build_db.connect()
        conn.execute("UPDATE artifacts SET sha256 = NULL")
        conn.commit()

        db_artifacts.usage_report(verify=True)

        out = capsys.readouterr().out
        assert "1 artifact(s): no sha256 recorded, not verifiable" in out

    def test_verify_silent_when_unmodified(self, tmp_path, capsys):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, None)

        db_artifacts.usage_report(verify=True)

        out = capsys.readouterr().out
        assert "sha256 mismatch" not in out
        assert "not verifiable" not in out


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

    def test_higher_version_kept_even_with_older_mtime(self, tmp_path):
        """docs/BUGS.md BUG-0017: a rebuild that produces an older version but
        lands on disk with a *later* mtime (a pin rollback, a corrected
        pinned-version) must not get kept over the genuinely newer version."""
        newer = tmp_path / "a-2.rpm"
        older = tmp_path / "a-1.rpm"
        _artifact(tmp_path, "a-2.rpm", "a", "rpm", 100, mtime=1, version="0.14.2-2.fc44")
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=2, version="0.14.2-1.fc44")

        db_artifacts.prune(confirm=True)

        assert newer.exists()
        assert not older.exists()

    def test_unversioned_rows_fall_back_to_mtime(self, tmp_path):
        """Rows with no recorded version (version=None) compare equal on the
        version key, so mtime remains the tiebreaker."""
        older = tmp_path / "a-1.rpm"
        newer = tmp_path / "a-2.rpm"
        _artifact(tmp_path, "a-1.rpm", "a", "rpm", 100, mtime=1)
        _artifact(tmp_path, "a-2.rpm", "a", "rpm", 100, mtime=2)

        db_artifacts.prune(confirm=True)

        assert newer.exists()
        assert not older.exists()

    def test_vendor_store_entry_removes_whole_directory(self, tmp_path):
        """A vendor-store row's path is the tarball inside a <pkg>/<hash>/
        entry dir that also holds meta.json (lib.vendor_store) -- pruning it
        must reclaim the whole entry, not leave meta.json/an empty dir behind.
        """
        import os

        old_dir = tmp_path / "vendor-store" / "pkg" / "hash-old"
        new_dir = tmp_path / "vendor-store" / "pkg" / "hash-new"
        old_dir.mkdir(parents=True)
        new_dir.mkdir(parents=True)
        (old_dir / "vendor.tar.gz").write_bytes(b"x" * 100)
        (old_dir / "meta.json").write_text("{}")
        (new_dir / "vendor.tar.gz").write_bytes(b"x" * 100)
        (new_dir / "meta.json").write_text("{}")
        os.utime(old_dir / "vendor.tar.gz", (1, 1))
        os.utime(new_dir / "vendor.tar.gz", (2, 2))
        build_db.record_artifact(
            str(old_dir / "vendor.tar.gz"), "vendor-store", "vendor", "pkg", "vendor-store", "1.0.0"
        )
        build_db.record_artifact(
            str(new_dir / "vendor.tar.gz"), "vendor-store", "vendor", "pkg", "vendor-store", "1.0.0"
        )

        db_artifacts.prune(confirm=True)

        assert not old_dir.exists()
        assert new_dir.exists()
        assert (new_dir / "meta.json").exists()
        remaining = build_db.artifacts(package="pkg", kind="vendor")
        assert len(remaining) == 1
        assert remaining[0]["path"] == str(new_dir / "vendor.tar.gz")


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


class TestForgetRepo:
    """--forget-repo TARGET drops local-repo ledger rows for one target, used
    by the fixed `make clean-localrepo` (docs/CHANGELOG.md 2026-08-11) to keep
    the artifact ledger honest after `rm -rf local-repo/<target>/`."""

    def test_removes_only_repo_rpm_rows_for_target(self, tmp_path, capsys):
        _artifact(tmp_path, "a.rpm", "a", "rpm", 100, mtime=1, target=TARGET)
        _artifact(
            tmp_path, "a-43.rpm", "a", "rpm", 100, mtime=1, target="fedora-43-x86_64"
        )
        # Non-repo realm rows (e.g. rpmbuild-volume srpms) must survive untouched.
        f = tmp_path / "a.src.rpm"
        f.write_bytes(b"x")
        build_db.record_artifact(str(f), "rpmbuild-volume", "srpm", "a", TARGET, None)
        # A mock_log row for the same target must also survive -- only rpm rows go.
        log = tmp_path / "20-mock.log"
        log.write_text("log")
        build_db.record_artifact(str(log), "repo", "mock_log", "a", TARGET, None)

        db_artifacts.forget_repo(TARGET)

        remaining = build_db.artifacts(package="a")
        remaining_targets_kinds = {
            (r["target"], r["kind"], r["realm"]) for r in remaining
        }
        assert (TARGET, "rpm", "repo") not in remaining_targets_kinds
        assert ("fedora-43-x86_64", "rpm", "repo") in remaining_targets_kinds
        assert (TARGET, "srpm", "rpmbuild-volume") in remaining_targets_kinds
        assert (TARGET, "mock_log", "repo") in remaining_targets_kinds
        assert TARGET in capsys.readouterr().out


class TestResolvePath:
    """#COPR-0015, #BUG-0062: db_artifacts._resolve_path()."""

    def test_recorded_path_resolves_directly(self, tmp_path):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x")
        row = {"path": str(f), "realm": "repo"}
        assert db_artifacts._resolve_path(row) == f

    def test_container_path_falls_back_to_host_path(self, tmp_path, monkeypatch):
        from lib import paths as paths_module

        monkeypatch.setattr(paths_module, "ROOT", tmp_path)
        (tmp_path / "local-repo" / TARGET).mkdir(parents=True)
        real = tmp_path / "local-repo" / TARGET / "a.rpm"
        real.write_bytes(b"x")

        row = {"path": f"/work/local-repo/{TARGET}/a.rpm", "realm": "repo"}
        assert db_artifacts._resolve_path(row) == real

    def test_rpmbuild_volume_unresolvable_returns_none(self):
        row = {"path": "/root/rpmbuild/SRPMS/a.src.rpm", "realm": "rpmbuild-volume"}
        assert db_artifacts._resolve_path(row) is None

    def test_genuinely_missing_file_returns_none(self, tmp_path):
        row = {"path": str(tmp_path / "gone.rpm"), "realm": "repo"}
        assert db_artifacts._resolve_path(row) is None


class TestUsageReportHostResolution:
    def test_rpmbuild_volume_row_reported_unresolvable_not_missing(self, capsys):
        build_db.record_artifact(
            "/root/rpmbuild/SRPMS/a.src.rpm", "rpmbuild-volume", "srpm", "a", TARGET, None
        )

        db_artifacts.usage_report()

        out = capsys.readouterr().out
        assert "no host path exists for this realm" in out
        assert "file missing on disk" not in out


class TestExportSnapshot:
    def test_yaml_export_contains_all_tables(self, tmp_path, capsys):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", TARGET, run_id, "success")
        f = tmp_path / "a.rpm"
        f.write_bytes(b"x")
        build_db.record_artifact(str(f), "repo", "rpm", "a", TARGET, "1.0-1.fc44")

        db_artifacts.export_snapshot("yaml", None)

        out = capsys.readouterr().out
        assert "runs:" in out
        assert "stage_results:" in out
        assert "stage_history:" in out
        assert "artifacts:" in out
        assert "a.rpm" in out

    def test_json_export_is_valid_json(self, capsys):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", TARGET, run_id, "success")

        db_artifacts.export_snapshot("json", None)

        import json

        out = capsys.readouterr().out
        data = json.loads(out)
        assert set(data.keys()) == {"runs", "stage_results", "stage_history", "artifacts"}

    def test_export_to_file(self, tmp_path):
        build_db.start_run(TARGET, "fedora", "44", "x86_64")
        output = tmp_path / "snapshot.yaml"

        db_artifacts.export_snapshot("yaml", str(output))

        assert output.exists()
        assert "runs:" in output.read_text()

    def test_two_exports_with_no_changes_are_identical(self):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", TARGET, run_id, "success")

        first = build_db.export_snapshot()
        second = build_db.export_snapshot()

        assert first == second
