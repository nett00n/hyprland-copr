"""Integration tests for make targets and pipeline components."""

import os
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
        ), patch.object(full_cycle, "report_copr_failures"):
            # Should not raise SystemExit
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

    def test_sync_copr_failed_is_failure(self):
        """When SYNCHRONOUS_COPR_BUILD=true, 'failed' COPR state is failure."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "copr", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), patch.object(
            full_cycle, "report_copr_failures"
        ) as mock_report_copr, pytest.raises(SystemExit) as exc:
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=True)

        assert exc.value.code == 1
        mock_report_copr.assert_called_once_with(packages, full_cycle.BUILD_LOG_DIR)

    def test_async_copr_failed_state_does_not_report(self):
        """Async mode: a 'failed' copr state doesn't drive exit or log analysis here --
        it only becomes terminal later, when gen-report.py polls (see
        lib.copr.poll_copr_status), and that's where the failed chroots'
        logs get fetched.
        """
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "copr", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), patch.object(full_cycle, "report_copr_failures") as mock_report_copr:
            # Should not raise SystemExit -- copr is excluded from any_failed when async.
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

        mock_report_copr.assert_not_called()

    def test_non_copr_failed_always_fails(self):
        """Failed spec/srpm/mock stage always fails, regardless of sync setting."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "failed")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), patch.object(full_cycle, "report_copr_failures"), pytest.raises(
            SystemExit
        ) as exc:
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
        ), patch.object(full_cycle, "report_copr_failures"):
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
        ), patch.object(full_cycle, "report_copr_failures"):
            # Should not raise SystemExit -- "some-other-pkg" isn't in `packages`.
            full_cycle.finalize_report(packages, TARGET, run_id, "", synchronous_copr=False)

    def test_finish_run_records_exit_state(self):
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")

        with patch.object(full_cycle, "print_summary"), patch.object(
            full_cycle, "report_mock_failures"
        ), patch.object(full_cycle, "report_copr_failures"):
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


class TestCoprGatedByChrootCoverage:
    """Coverage for docs/bugs.md BUG-0018's pre-submit gate: REQUIRE_CHROOT_COVERAGE=true
    must block Copr submission the same way a mock failure already does, while the
    default (unset) behavior only warns and still submits.
    """

    def _run(self, coverage_ok, require_coverage=False):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        def fake_mock_run_for_package(
            pkg, meta, fedora_version, target, proceed, mock_failed, all_pkgs, run_id_
        ):
            build_db.set_stage(pkg, "mock", target, run_id_, "success")
            mock_failed[pkg] = False
            return True

        def fake_is_cached(stage, pkg, target, new_hashes, forced_stages):
            return stage not in ("mock", "copr")

        with patch.object(
            full_cycle, "get_packages", return_value=packages
        ), patch.object(
            full_cycle, "compute_input_hashes", return_value={}
        ), patch.object(
            full_cycle, "effective_deps", return_value=set()
        ), patch.object(
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
        ) as copr_mock, patch.object(
            full_cycle, "print_chroot_coverage", return_value=coverage_ok
        ), patch.dict(
            os.environ, {"REQUIRE_CHROOT_COVERAGE": "true" if require_coverage else ""}
        ):
            full_cycle.run_build_pipeline(
                packages,
                TARGET,
                run_id,
                fedora_version="44",
                copr_repo="nett00n/hyprland",
                proceed=False,
                skip_copr=False,
            )

        return copr_mock

    def test_require_coverage_blocks_on_gap(self):
        copr_mock = self._run(coverage_ok=False, require_coverage=True)

        copr_mock.assert_not_called()
        entry = build_db.get_stage("hyprutils", "copr", TARGET)
        assert entry["reason"] == "blocked: chroot coverage"

    def test_default_warns_but_still_submits(self):
        copr_mock = self._run(coverage_ok=False, require_coverage=False)

        assert copr_mock.call_count == 2

    def test_require_coverage_does_not_block_when_covered(self):
        copr_mock = self._run(coverage_ok=True, require_coverage=True)

        assert copr_mock.call_count == 2


class TestFullCycleMatrixTarget:
    """`make -n` dry-run coverage for the full-cycle-matrix target added for
    docs/bugs.md BUG-0018: it must loop per-version full-cycle with SKIP_COPR=true,
    then submit to Copr exactly once (only when COPR_REPO is set).
    """

    def test_loops_versions_with_skip_copr(self):
        # -n on the outer invocation propagates to the recursive $(MAKE) calls
        # via MAKEFLAGS (GNU make special-cases lines referencing $(MAKE): the
        # `for` loop itself runs for real -- hence the two real "Fedora NN"
        # echoes below -- but each nested `make full-cycle` still inherits -n
        # and only prints what it would do).
        result = subprocess.run(
            ["make", "-n", "full-cycle-matrix", "MATRIX_VERSIONS=43 44", "COPR_REPO="],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Fedora 43" in result.stdout
        assert "Fedora 44" in result.stdout
        assert "FEDORA_VERSION=43" in result.stdout
        assert "FEDORA_VERSION=44" in result.stdout
        # >=2: one per real per-version dry-run submake, plus the literal (unexpanded
        # "$v") text of the for-loop recipe line itself that -n always echoes first.
        assert result.stdout.count("SKIP_COPR=true") >= 2
        # The `if [ -n "$(COPR_REPO)" ]; then make stage-copr ...` line also contains
        # $(MAKE), so -n echoes its raw source text (which mentions "stage-copr")
        # regardless of which branch runs -- that's not a reliable signal. Whether
        # `make stage-copr` was actually invoked is: did its own recipe body (which
        # names the script path) get dry-run-printed in turn.
        assert "COPR_REPO not set -- skipping Copr submission" in result.stdout
        assert "scripts/stage-copr.py" not in result.stdout

    def test_submits_to_copr_once_when_repo_set(self):
        result = subprocess.run(
            [
                "make",
                "-n",
                "full-cycle-matrix",
                "MATRIX_VERSIONS=43",
                "COPR_REPO=nett00n/hyprland",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert result.stdout.count("Fedora 43") == 1
        # Real invocation this time (COPR_REPO set) -- its own recipe body,
        # naming the script, gets dry-run-printed in turn.
        assert "scripts/stage-copr.py" in result.stdout


class TestPackageVarSemantics:
    """Coverage for docs/todo.md TODO-0029: PACKAGE meant three different things across
    targets with no validation. Single-package-only targets now reject a comma-separated
    PACKAGE with a clear error instead of a confusing downstream one, and gather-requires
    (a filesystem path to a built .rpm, not a packages.yaml key) now takes RPM= instead.
    """

    NO_CONTAINER_ENV = {**os.environ, "NO_CONTAINER": "1"}

    def _run_comma_guard(self, target: str, extra_args: list[str] | None = None):
        return subprocess.run(
            ["make", target, "PACKAGE=a,b", *(extra_args or [])],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=self.NO_CONTAINER_ENV,
        )

    def test_add_submodule_rejects_comma_list(self):
        result = self._run_comma_guard("add-submodule")
        assert result.returncode != 0
        assert "single package name" in result.stdout

    def test_delete_package_rejects_comma_list(self):
        result = self._run_comma_guard("delete-package")
        assert result.returncode != 0
        assert "single package name" in result.stdout

    def test_scaffold_package_rejects_comma_list(self):
        result = self._run_comma_guard("scaffold-package")
        assert result.returncode != 0
        assert "single package name" in result.stdout

    def test_list_tags_rejects_comma_list(self):
        result = self._run_comma_guard("list-tags")
        assert result.returncode != 0
        assert "single package name" in result.stdout

    def test_comma_guard_pattern_does_not_match_empty_or_single_name(self):
        """The `case "$(PACKAGE)" in *,*)` guard shell pattern must only match an actual
        comma-separated list -- not empty PACKAGE (meaning "all" on list-tags) or a plain
        single name. `make -n` can't verify this: -n echoes recipe text unconditionally
        without evaluating the shell `case`, so it "sees" the guard's own error message
        text regardless of whether it would really fire. Exercise the exact pattern
        against the shell directly instead.
        """
        guard = 'case "{}" in *,*) echo MATCHED;; *) echo NO_MATCH;; esac'
        for value, expected in [("", "NO_MATCH"), ("hyprutils", "NO_MATCH"), ("a,b", "MATCHED")]:
            result = subprocess.run(
                ["sh", "-c", guard.format(value)], capture_output=True, text=True
            )
            assert result.stdout.strip() == expected, f"PACKAGE={value!r}"

    def test_gather_requires_uses_rpm_var(self):
        result = subprocess.run(
            ["make", "-n", "gather-requires", "RPM=local-repo/hyprutils-0.14.0.fc44.x86_64.rpm"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "gather-requires.py local-repo/hyprutils-0.14.0.fc44.x86_64.rpm" in result.stdout
        assert "PACKAGE=" not in result.stdout

    def test_gather_requires_missing_rpm_errors(self):
        result = subprocess.run(
            ["make", "gather-requires"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=self.NO_CONTAINER_ENV,
        )
        assert result.returncode != 0
        assert "RPM is required" in result.stdout

    def test_pkgs_expands_comma_list_to_space_separated(self):
        """sources/stage-log-analyze's shell `for pkg in $(_PKGS)` loop needs space-separated
        words; PACKAGE=a,b must not become one literal 'a,b' token (the pre-fix behavior)."""
        result = subprocess.run(
            ["make", "-p", "-n", "PACKAGE=a,b"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "_PKGS := a b" in result.stdout
        assert "_PKGS := a,b" not in result.stdout


class TestUpdateDailyResilience:
    """Coverage for docs/todo.md TODO-0061 (a failed package build must not abort readme/
    copr-description/git commit) and TODO-0064 (nightly gate is validate-packages+fmt only,
    not the full pre-commit test+lint+fmt gate) via `make -n update-daily` dry-run text.
    """

    def _dry_run(self):
        result = subprocess.run(
            ["make", "-n", "update-daily", "COPR_REPO=nett00n/hyprland"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    def test_gate_is_validate_and_fmt_not_full_pre_commit(self):
        stdout = self._dry_run()
        assert "make validate-packages fmt" in stdout
        # The full developer gate (test+lint) must not run as part of update-daily.
        assert "pytest tests/" not in stdout
        assert "ruff check" not in stdout

    def test_full_cycle_failure_does_not_abort_chain(self):
        stdout = self._dry_run()
        assert "make full-cycle || touch logs/.update-daily-failed" in stdout
        # readme/copr-description and the git commit block must appear AFTER the
        # full-cycle line, i.e. not gated behind its success.
        full_cycle_pos = stdout.index("make full-cycle || touch")
        readme_pos = stdout.index("make readme copr-description")
        commit_pos = stdout.index('git commit -m "Daily update:')
        marker_check_pos = stdout.index("if [ -f logs/.update-daily-failed ]")
        assert full_cycle_pos < readme_pos < commit_pos < marker_check_pos

    def test_stale_marker_cleared_at_start(self):
        stdout = self._dry_run()
        assert "mkdir -p logs && rm -f logs/.update-daily-failed" in stdout

    def test_stage_log_analyze_runs_after_readme_before_commit(self):
        """Coverage for docs/bugs.md BUG-0041: full-cycle.py's next run rmtree's
        logs/build/<pkg> before building, so any night's mock/Copr failure logs
        must be analyzed *this* night or they're destroyed unread. Must run after
        readme (whose gen-report.py poll fetches newly-failed Copr chroot logs)
        and must not abort the chain -- pkg-log-analysis.py exits non-zero to mean
        "issues found", not "this recipe failed".
        """
        stdout = self._dry_run()
        assert "make stage-log-analyze || true" in stdout
        readme_pos = stdout.index("make readme copr-description")
        analyze_pos = stdout.index("make stage-log-analyze || true")
        commit_pos = stdout.index('git commit -m "Daily update:')
        assert readme_pos < analyze_pos < commit_pos


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
