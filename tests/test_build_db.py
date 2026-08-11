"""Tests for lib.build_db: SQLite storage for build-report data.

No consumers exist yet (phase 1 of the yaml->sqlite migration) -- this
module is tested in isolation before any stage script is repointed at it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


class TestSchema:
    def test_fresh_db_creates_schema_at_current_user_version(self, build_db_path):
        conn = build_db.connect()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == build_db.SCHEMA_VERSION

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"runs", "stage_results", "artifacts"} <= tables

    def test_connect_is_idempotent_on_existing_db(self, build_db_path):
        build_db.connect()
        build_db.close()
        # Reconnecting to the same on-disk db must not raise or reset data.
        build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.close()
        conn = build_db.connect()
        rows = conn.execute("SELECT * FROM runs").fetchall()
        assert len(rows) == 1

    def test_connect_reads_paths_build_db_at_call_time(self, tmp_path, monkeypatch):
        """The path is resolved fresh on each connect(), not bound at def-time."""
        path_a = tmp_path / "a.db"
        monkeypatch.setattr(paths, "BUILD_DB", path_a)
        build_db.connect()
        assert path_a.exists()

        path_b = tmp_path / "b.db"
        monkeypatch.setattr(paths, "BUILD_DB", path_b)
        build_db.connect()
        assert path_b.exists()


class TestStageResultsKey:
    def test_same_package_two_targets_coexist(self, build_db_path):
        run_id = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-43-x86_64", run_id, "success", version="0.14.0-1.fc43")
        run_id_44 = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", "fedora-44-x86_64", run_id_44, "success", version="0.14.0-2.fc44")

        entry_43 = build_db.get_stage("hyprutils", "mock", "fedora-43-x86_64")
        entry_44 = build_db.get_stage("hyprutils", "mock", "fedora-44-x86_64")
        assert entry_43["version"] == "0.14.0-1.fc43"
        assert entry_44["version"] == "0.14.0-2.fc44"

    def test_target_key_accepts_non_fedora_and_non_x86_values(self, build_db_path):
        """Forward-compat check: the schema doesn't hardcode fedora/x86_64 anywhere."""
        run_id = build_db.start_run(
            "centos-stream-10-aarch64", "centos-stream", "10", "aarch64"
        )
        build_db.set_stage(
            "hyprutils", "mock", "centos-stream-10-aarch64", run_id, "success", version="0.14.0-1.el10"
        )
        entry = build_db.get_stage("hyprutils", "mock", "centos-stream-10-aarch64")
        assert entry["version"] == "0.14.0-1.el10"


class TestSetStage:
    def test_set_stage_roundtrips_all_columns(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage(
            "ashell",
            "copr",
            "fedora-44-x86_64",
            run_id,
            "success",
            version="0.9.0-6.fc44",
            reason="hash-mismatch",
            log="logs/build/ashell/30-copr.log",
            build_id=10778749,
            has_devel=1,
            force_run=0,
        )
        entry = build_db.get_stage("ashell", "copr", "fedora-44-x86_64")
        assert entry["state"] == "success"
        assert entry["version"] == "0.9.0-6.fc44"
        assert entry["reason"] == "hash-mismatch"
        assert entry["log"] == "logs/build/ashell/30-copr.log"
        assert entry["build_id"] == 10778749
        assert entry["has_devel"] == 1

    def test_set_stage_upserts_on_repeat(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "failed")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "success", version="1.0-1.fc44")

        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert entry["state"] == "success"
        assert entry["version"] == "1.0-1.fc44"

        conn = build_db.connect()
        count = conn.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0]
        assert count == 1

    def test_set_stage_replaces_row_and_clears_hashes(self, build_db_path):
        """set_stage mirrors dict-replace semantics: a fresh call wipes stale hashes."""
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "success")
        build_db.finalize_stage(
            "ashell", "spec", "fedora-44-x86_64", started_at=100, hashes={"a": "b"}
        )
        assert build_db.get_stage("ashell", "spec", "fedora-44-x86_64")["hashes"] == {"a": "b"}

        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "failed")
        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert "hashes" not in entry


class TestUpdateReason:
    def test_update_reason_leaves_other_columns_untouched(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "success", version="1.0-1.fc44")
        build_db.finalize_stage(
            "ashell", "spec", "fedora-44-x86_64", started_at=100, hashes={"a": "b"}
        )

        build_db.update_reason("ashell", "spec", "fedora-44-x86_64", "cached")

        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert entry["reason"] == "cached"
        assert entry["version"] == "1.0-1.fc44"
        assert entry["hashes"] == {"a": "b"}


class TestUpdateState:
    def test_update_state_leaves_other_columns_untouched(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage(
            "ashell", "copr", "fedora-44-x86_64", run_id, "unknown", build_id=123
        )

        build_db.update_state("ashell", "copr", "fedora-44-x86_64", "success")

        entry = build_db.get_stage("ashell", "copr", "fedora-44-x86_64")
        assert entry["state"] == "success"
        assert entry["build_id"] == 123

    def test_update_state_noop_when_row_absent(self, build_db_path):
        build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        # No error, no row created.
        build_db.update_state("nonexistent", "copr", "fedora-44-x86_64", "success")
        assert build_db.get_stage("nonexistent", "copr", "fedora-44-x86_64") is None


class TestFinalizeStage:
    def test_finalize_stage_stamps_started_at_and_clears_force_run(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "success", force_run=1)

        build_db.finalize_stage(
            "ashell", "spec", "fedora-44-x86_64", started_at=123, hashes={"x": "y"}
        )

        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert entry["started_at"] == 123
        assert entry.get("force_run", 0) == 0
        assert entry["hashes"] == {"x": "y"}

    def test_finalize_stage_skips_hashes_when_state_not_success(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "failed")

        build_db.finalize_stage(
            "ashell", "spec", "fedora-44-x86_64", started_at=123, hashes={"x": "y"}
        )

        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert "hashes" not in entry

    def test_finalize_stage_preserves_hashes_when_update_hashes_false(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("ashell", "spec", "fedora-44-x86_64", run_id, "success")
        build_db.finalize_stage(
            "ashell", "spec", "fedora-44-x86_64", started_at=100, hashes={"old": "1"}
        )

        build_db.finalize_stage(
            "ashell",
            "spec",
            "fedora-44-x86_64",
            started_at=200,
            hashes={"new": "2"},
            update_hashes=False,
        )

        entry = build_db.get_stage("ashell", "spec", "fedora-44-x86_64")
        assert entry["hashes"] == {"old": "1"}
        assert entry["started_at"] == 200

    def test_finalize_stage_ignores_nonexistent_entry(self, build_db_path):
        build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        # No error, no row created.
        build_db.finalize_stage(
            "nonexistent", "spec", "fedora-44-x86_64", started_at=1, hashes={}
        )
        assert build_db.get_stage("nonexistent", "spec", "fedora-44-x86_64") is None


class TestClearStage:
    def test_clear_stage_removes_only_listed_packages(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        for pkg in ("a", "b", "c"):
            build_db.set_stage(pkg, "mock", "fedora-44-x86_64", run_id, "success")

        build_db.clear_stage("mock", "fedora-44-x86_64", packages=["a"])

        assert build_db.get_stage("a", "mock", "fedora-44-x86_64") is None
        assert build_db.get_stage("b", "mock", "fedora-44-x86_64") is not None
        assert build_db.get_stage("c", "mock", "fedora-44-x86_64") is not None

    def test_clear_stage_leaves_other_targets_alone(self, build_db_path):
        run_id_43 = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        run_id_44 = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-43-x86_64", run_id_43, "success")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id_44, "success")

        build_db.clear_stage("mock", "fedora-44-x86_64", packages=["a"])

        assert build_db.get_stage("a", "mock", "fedora-43-x86_64") is not None
        assert build_db.get_stage("a", "mock", "fedora-44-x86_64") is None

    def test_clear_stage_leaves_other_stages_alone(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")
        build_db.set_stage("a", "spec", "fedora-44-x86_64", run_id, "success")

        build_db.clear_stage("mock", "fedora-44-x86_64", packages=["a"])

        assert build_db.get_stage("a", "mock", "fedora-44-x86_64") is None
        assert build_db.get_stage("a", "spec", "fedora-44-x86_64") is not None


class TestStageMap:
    def test_stage_map_orders_packages_deterministically(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        for pkg in ("zeta", "alpha", "mu"):
            build_db.set_stage(pkg, "mock", "fedora-44-x86_64", run_id, "success")

        result_1 = build_db.stage_map("fedora-44-x86_64")
        result_2 = build_db.stage_map("fedora-44-x86_64")
        assert list(result_1["mock"].keys()) == list(result_2["mock"].keys())

    def test_stage_map_filters_by_stage(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")
        build_db.set_stage("a", "spec", "fedora-44-x86_64", run_id, "success")

        result = build_db.stage_map("fedora-44-x86_64", stage="mock")
        assert "mock" in result
        assert "spec" not in result

    def test_stage_map_filters_by_packages(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")
        build_db.set_stage("b", "mock", "fedora-44-x86_64", run_id, "success")

        result = build_db.stage_map("fedora-44-x86_64", packages=["a"])
        assert list(result["mock"].keys()) == ["a"]


class TestForceRun:
    def test_set_force_run_flags_matching_rows_and_returns_affected(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")
        build_db.set_stage("a", "copr", "fedora-44-x86_64", run_id, "success")

        affected = build_db.set_force_run(["a", "nonexistent"], ("mock", "copr"), "fedora-44-x86_64")

        assert affected == ["a"]
        assert build_db.get_stage("a", "mock", "fedora-44-x86_64")["force_run"] == 1
        assert build_db.get_stage("a", "copr", "fedora-44-x86_64")["force_run"] == 1


class TestForgetPackage:
    def test_forget_package_removes_rows_across_targets(self, build_db_path):
        run_id_43 = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        run_id_44 = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-43-x86_64", run_id_43, "success")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id_44, "success")
        build_db.set_stage("b", "mock", "fedora-44-x86_64", run_id_44, "success")

        build_db.forget_package("a")

        assert build_db.get_stage("a", "mock", "fedora-43-x86_64") is None
        assert build_db.get_stage("a", "mock", "fedora-44-x86_64") is None
        assert build_db.get_stage("b", "mock", "fedora-44-x86_64") is not None


class TestDeleteArtifactsForTarget:
    """Used by `db-artifacts.py --forget-repo` (the fixed `make clean-localrepo`,
    docs/CHANGELOG.md 2026-08-11) to drop ledger rows for one target's local-repo
    RPMs after `rm -rf local-repo/<target>/`."""

    def test_deletes_only_matching_realm_kind_target(self, build_db_path, tmp_path):
        matching = tmp_path / "a.rpm"
        matching.write_bytes(b"x")
        build_db.record_artifact(
            str(matching), "repo", "rpm", "a", "fedora-44-x86_64", "1.0-1.fc44"
        )
        other_target = tmp_path / "a-43.rpm"
        other_target.write_bytes(b"x")
        build_db.record_artifact(
            str(other_target), "repo", "rpm", "a", "fedora-43-x86_64", "1.0-1.fc43"
        )
        other_kind = tmp_path / "20-mock.log"
        other_kind.write_text("log")
        build_db.record_artifact(
            str(other_kind), "repo", "mock_log", "a", "fedora-44-x86_64", None
        )
        other_realm = tmp_path / "a.src.rpm"
        other_realm.write_bytes(b"x")
        build_db.record_artifact(
            str(other_realm), "rpmbuild-volume", "srpm", "a", "fedora-44-x86_64", None
        )

        build_db.delete_artifacts_for_target("fedora-44-x86_64", "repo", "rpm")

        remaining = {r["path"] for r in build_db.artifacts(package="a")}
        assert str(matching) not in remaining
        assert str(other_target) in remaining
        assert str(other_kind) in remaining
        assert str(other_realm) in remaining


class TestArtifacts:
    def test_record_artifact_stores_size_and_mtime(self, build_db_path, tmp_path):
        f = tmp_path / "pkg.rpm"
        f.write_bytes(b"x" * 1024)

        build_db.record_artifact(str(f), "repo", "rpm", "pkg", "fedora-44-x86_64", "1.0-1.fc44")

        rows = build_db.artifacts(package="pkg")
        assert len(rows) == 1
        assert rows[0]["size_bytes"] == 1024
        assert rows[0]["mtime"] is not None

    def test_record_artifact_upserts_on_same_path(self, build_db_path, tmp_path):
        f = tmp_path / "pkg.rpm"
        f.write_bytes(b"x" * 10)
        build_db.record_artifact(str(f), "repo", "rpm", "pkg", "fedora-44-x86_64", "1.0-1.fc44")
        f.write_bytes(b"x" * 20)
        build_db.record_artifact(str(f), "repo", "rpm", "pkg", "fedora-44-x86_64", "1.0-2.fc44")

        rows = build_db.artifacts(package="pkg")
        assert len(rows) == 1
        assert rows[0]["size_bytes"] == 20
        assert rows[0]["version"] == "1.0-2.fc44"

    def test_artifacts_filters_by_package_kind_and_target(self, build_db_path, tmp_path):
        f1 = tmp_path / "a-1.fc44.rpm"
        f1.write_bytes(b"1")
        f2 = tmp_path / "a.log"
        f2.write_bytes(b"1")
        f3 = tmp_path / "a-1.fc43.rpm"
        f3.write_bytes(b"1")
        build_db.record_artifact(str(f1), "repo", "rpm", "a", "fedora-44-x86_64", None)
        build_db.record_artifact(str(f2), "repo", "log", "a", "fedora-44-x86_64", None)
        build_db.record_artifact(str(f3), "repo", "rpm", "a", "fedora-43-x86_64", None)

        assert len(build_db.artifacts(package="a", kind="rpm")) == 2
        assert len(build_db.artifacts(package="a", kind="rpm", target="fedora-44-x86_64")) == 1

    def test_delete_artifact_removes_row(self, build_db_path, tmp_path):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"1")
        build_db.record_artifact(str(f), "repo", "rpm", "a", "fedora-44-x86_64", None)

        build_db.delete_artifact("repo", str(f))

        assert build_db.artifacts(package="a") == []


class TestRuns:
    def test_start_and_finish_run_record_timestamps_and_exit_state(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64", copr_repo="nett00n/hyprland")
        build_db.finish_run(run_id, "ok")

        conn = build_db.connect()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row["exit_state"] == "ok"
        assert row["completed_at"] is not None
        assert row["copr_repo"] == "nett00n/hyprland"

    def test_latest_run_on_empty_db_returns_none(self, build_db_path):
        assert build_db.latest_run("fedora-44-x86_64") is None

    def test_latest_run_returns_most_recent_row_for_target(self, build_db_path):
        build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        run_id_2 = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")

        result = build_db.latest_run("fedora-44-x86_64")
        assert result["id"] == run_id_2

    def test_latest_run_scoped_to_target(self, build_db_path):
        build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        assert build_db.latest_run("fedora-44-x86_64") is None


class TestRowDictNullHandling:
    def test_row_dict_omits_null_columns(self, build_db_path):
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "validate", "fedora-44-x86_64", run_id, "success")

        entry = build_db.get_stage("a", "validate", "fedora-44-x86_64")
        # errors/warnings/version/reason were never passed -> must be absent, not None.
        assert "errors" not in entry
        assert "warnings" not in entry
        assert "version" not in entry
        assert "reason" not in entry


class TestResetOrdering:
    def test_reset_deletes_in_fk_safe_order(self, build_db_path):
        """stage_results.run_id references runs(id); deleting runs first must not raise."""
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")

        build_db.reset()

        conn = build_db.connect()
        assert conn.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0

    def test_reset_preserves_artifacts(self, build_db_path, tmp_path):
        f = tmp_path / "a.rpm"
        f.write_bytes(b"1")
        run_id = build_db.start_run("fedora-44-x86_64", "fedora", "44", "x86_64")
        build_db.set_stage("a", "mock", "fedora-44-x86_64", run_id, "success")
        build_db.record_artifact(str(f), "repo", "rpm", "a", "fedora-44-x86_64", "1-1.fc44")

        build_db.reset()

        assert len(build_db.artifacts(package="a")) == 1
