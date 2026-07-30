"""Integration tests for make targets and pipeline components."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import using importlib to handle module names with dashes
import importlib

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib import build_db, paths

full_cycle = importlib.import_module("scripts.full-cycle")
stage_copr = importlib.import_module("scripts.stage-copr")
stage_vendor = importlib.import_module("scripts.stage-vendor")
stage_srpm = importlib.import_module("scripts.stage-srpm")
stage_mock = importlib.import_module("scripts.stage-mock")
stage_show_plan = importlib.import_module("scripts.stage-show-plan")

ROOT = Path(__file__).parent.parent.parent

TARGET = "fedora-44-x86_64"


def run_make(target: str, env=None, **kwargs) -> subprocess.CompletedProcess:
    """Run 'make <target>' in repo root, capture output."""
    return subprocess.run(
        ["make", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        **kwargs,
    )


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


class TestFullCycleFinalize:
    """Test finalize_report() with async/sync COPR builds.

    This is the critical test suite for the pipeline's exit behavior:
    - async COPR (SYNCHRONOUS_COPR_BUILD=false) with 'unknown' state should NOT fail
    - sync COPR (SYNCHRONOUS_COPR_BUILD=true) with 'failed' state SHOULD fail
    - any failed non-copr stage (spec/srpm/mock) should always fail
    - validate failures are ignored
    """

    def test_async_copr_unknown_state_not_failure(self):
        """When SYNCHRONOUS_COPR_BUILD=false, 'unknown' COPR state is valid."""
        packages = {"pkg1": {}, "pkg2": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        for pkg in packages:
            build_db.set_stage(pkg, "spec", TARGET, run_id, "success")
            build_db.set_stage(pkg, "copr", TARGET, run_id, "unknown")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ):
            # Should not raise SystemExit
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

    def test_sync_copr_failed_is_failure(self):
        """When SYNCHRONOUS_COPR_BUILD=true, 'failed' COPR state is failure."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "copr", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), pytest.raises(SystemExit) as exc:
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=True)

        assert exc.value.code == 1

    def test_non_copr_failed_always_fails(self):
        """Failed spec/srpm/mock stage always fails, regardless of sync setting."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), pytest.raises(SystemExit) as exc:
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

        assert exc.value.code == 1

    def test_validation_failure_ignored(self):
        """Validation stage failures do not cause pipeline failure."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "validate", TARGET, run_id, "failed")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ):
            # Should not raise SystemExit
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

    def test_only_considers_packages_in_this_run(self):
        """A failure recorded for a package outside this run's package set doesn't count.

        Regression coverage for issue #23: the old finalize_report scanned the
        WHOLE persisted report, so one stale failed row from an unrelated
        package made every future run exit non-zero.
        """
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")
        build_db.set_stage("some-other-pkg", "spec", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ):
            # Should not raise SystemExit -- "some-other-pkg" isn't in `packages`.
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

    def test_finish_run_records_exit_state(self):
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ):
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

        conn = build_db.connect()
        row = conn.execute("SELECT exit_state FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row["exit_state"] == "ok"


class TestMockFailedPackages:
    """Test mock_failed_packages(), the pure helper behind the Copr gate."""

    def test_no_failures(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", TARGET, run_id, "success")
        build_db.set_stage("Hyprland", "mock", TARGET, run_id, "success")
        assert full_cycle.mock_failed_packages(packages, TARGET) == []

    def test_one_failure(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", TARGET, run_id, "success")
        build_db.set_stage("Hyprland", "mock", TARGET, run_id, "failed")
        assert full_cycle.mock_failed_packages(packages, TARGET) == ["Hyprland"]

    def test_missing_entry_not_a_failure(self):
        """A package with no mock entry at all (e.g. skipped) isn't a 'failure'."""
        packages = {"pkg1": {}}
        build_db.start_run(TARGET, "fedora", "44", "x86_64")
        assert full_cycle.mock_failed_packages(packages, TARGET) == []

    def test_only_considers_packages_in_this_run(self):
        """A failure recorded for a package outside this run's set doesn't count."""
        packages = {"hyprutils": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "mock", TARGET, run_id, "success")
        build_db.set_stage("some-other-pkg", "mock", TARGET, run_id, "failed")
        assert full_cycle.mock_failed_packages(packages, TARGET) == []


class TestCoprGatedByMockFailure:
    """Regression coverage for issue #8: per-package pipelines used to submit
    each package to Copr as soon as its own mock succeeded, so a healthy early
    package (hyprutils) could already be public by the time a later, dependent
    package (Hyprland) failed mock. Copr submission must now be an all-or-nothing
    pass gated on every package's mock having succeeded this run.
    """

    def _run(self, packages, mock_outcomes, copr_repo="nett00n/hyprland", skip_copr=False):
        """Run run_build_pipeline with heavy mocking; return (target, run_id, copr_mock)."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        def fake_mock_run_for_package(
            pkg, meta, fedora_version, target, proceed, mock_failed, all_pkgs, run_id_
        ):
            ok = mock_outcomes[pkg]
            build_db.set_stage(pkg, "mock", target, run_id_, "success" if ok else "failed")
            mock_failed[pkg] = not ok
            return ok

        def fake_is_cached(stage, pkg, target, new_hashes, forced_stages):
            # Only mock/copr are "not cached" -- exercises the real branches.
            return stage not in ("mock", "copr")

        with patch.object(full_cycle, "get_packages", return_value=packages), patch.object(
            full_cycle, "compute_input_hashes", return_value={}
        ), patch.object(full_cycle, "effective_deps", return_value=set()), patch.object(
            full_cycle, "is_cached", side_effect=fake_is_cached
        ), patch.object(
            full_cycle, "cache_miss_reason", return_value="test"
        ), patch.object(
            full_cycle.time, "sleep"
        ), patch.object(
            full_cycle._stage["stage-show-plan"], "show_plan"
        ), patch.object(
            full_cycle._stage["stage-validate"], "run_global_checks"
        ), patch.object(
            full_cycle._stage["stage-validate"], "run_for_package", return_value=True
        ), patch.object(
            full_cycle._stage["stage-copr"], "check_copr_credentials"
        ), patch.object(
            full_cycle._stage["stage-mock"],
            "run_for_package",
            side_effect=fake_mock_run_for_package,
        ), patch.object(
            full_cycle._stage["stage-copr"], "run_for_package", return_value=True
        ) as copr_mock:
            full_cycle.run_build_pipeline(
                packages,
                TARGET,
                run_id,
                fedora_version="44",
                copr_repo=copr_repo,
                proceed=False,
                skip_copr=skip_copr,
            )

        return run_id, copr_mock

    def test_one_package_mock_failure_blocks_copr_for_all(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id, copr_mock = self._run(
            packages, {"hyprutils": True, "Hyprland": False}
        )

        # hyprutils succeeded its own mock build, but must NOT reach Copr.
        copr_mock.assert_not_called()
        hyprutils_entry = build_db.get_stage("hyprutils", "copr", TARGET)
        hyprland_entry = build_db.get_stage("Hyprland", "copr", TARGET)
        assert "blocked" in hyprutils_entry["reason"]
        assert "blocked" in hyprland_entry["reason"]
        assert "Hyprland" in hyprutils_entry["reason"]

    def test_all_mock_success_copr_runs_for_all(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id, copr_mock = self._run(
            packages, {"hyprutils": True, "Hyprland": True}
        )

        assert copr_mock.call_count == 2
        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert called_pkgs == {"hyprutils", "Hyprland"}

    def test_skip_copr_env_bypasses_gate_entirely(self):
        """SKIP_COPR=true still just skips -- no blocked-reason noise."""
        packages = {"hyprutils": {}, "Hyprland": {}}
        # Seed a prior successful copr entry, as a real repeated run would have.
        seed_run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "copr", TARGET, seed_run_id, "success")

        run_id, copr_mock = self._run(
            packages,
            {"hyprutils": False, "Hyprland": False},
            skip_copr=True,
        )

        copr_mock.assert_not_called()
        entry = build_db.get_stage("hyprutils", "copr", TARGET)
        assert entry["reason"] == "SKIP_COPR"


class TestInfoTargets:
    """Test informational make targets."""

    def test_help_target_prints_usage(self):
        """make help prints usage and exits 0."""
        result = run_make("help")

        assert result.returncode == 0
        assert "help" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_check_venv_with_existing_venv(self):
        """make check-venv exits 0 when .venv exists."""
        result = run_make("check-venv")

        # In the test environment, .venv should exist (from setup)
        assert result.returncode == 0


class TestSrpmBlocking:
    """Test SRPM stage blocking by spec failure."""

    def test_srpm_blocked_by_spec_failure(self):
        """SRPM skipped when spec stage failed."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "spec", TARGET, run_id, "failed")
        fedora_version = "44"

        result = stage_srpm.run_for_package(
            pkg, meta, fedora_version, proceed=False, target=TARGET, run_id=run_id
        )

        assert result is True
        entry = build_db.get_stage(pkg, "srpm", TARGET)
        assert entry["state"] == "skipped"
