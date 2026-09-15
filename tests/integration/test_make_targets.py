"""Integration tests for make targets and pipeline components."""

import contextlib
import fcntl
import os
import re
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

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures"),
        ):
            # Should not raise SystemExit
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

    def test_sync_copr_failed_is_failure(self):
        """When SYNCHRONOUS_COPR_BUILD=true, 'failed' COPR state is failure."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "copr", TARGET, run_id, "failed")

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures") as mock_report_copr,
            pytest.raises(SystemExit) as exc,
        ):
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=True
            )

        assert exc.value.code == 1
        mock_report_copr.assert_called_once_with(
            packages, full_cycle.BUILD_LOG_DIR, {"pkg1": "-"}
        )

    def test_async_copr_failed_state_does_not_report(self):
        """Async mode: a 'failed' copr state doesn't drive exit or log analysis here --
        it only becomes terminal later, when gen-report.py polls (see
        lib.copr.poll_copr_status), and that's where the failed chroots'
        logs get fetched.
        """
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "copr", TARGET, run_id, "failed")

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures") as mock_report_copr,
        ):
            # Should not raise SystemExit -- copr is excluded from any_failed when async.
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

        mock_report_copr.assert_not_called()

    def test_non_copr_failed_always_fails(self):
        """Failed spec/srpm/mock stage always fails, regardless of sync setting."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "failed")

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures"),
            pytest.raises(SystemExit) as exc,
        ):
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

        assert exc.value.code == 1

    def test_validation_failure_ignored(self):
        """Validation stage failures do not cause pipeline failure."""
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "validate", TARGET, run_id, "failed")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures"),
        ):
            # Should not raise SystemExit
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

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

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures"),
        ):
            # Should not raise SystemExit -- "some-other-pkg" isn't in `packages`.
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

    def test_finish_run_records_exit_state(self):
        packages = {"pkg1": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg1", "spec", TARGET, run_id, "success")

        with (
            patch.object(full_cycle, "print_summary"),
            patch.object(full_cycle, "report_mock_failures"),
            patch.object(full_cycle, "report_copr_failures"),
        ):
            full_cycle.finalize_report(
                packages, TARGET, run_id, "", synchronous_copr=False
            )

        conn = build_db.connect()
        row = conn.execute(
            "SELECT exit_state FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
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


@contextlib.contextmanager
def _patched_pipeline(
    mock_side_effect,
    is_cached_side_effect=None,
    coverage_ok=True,
    require_coverage=False,
    spy_forced_stages=False,
):
    """Patch every stage full_cycle.run_build_pipeline touches except the Copr/mock
    gating logic itself, which is what these tests actually exercise.

    stage-vendor is patched too (BUG-0045's vendor_decision() now calls
    stage-vendor.run_for_package() for the "not-applicable" case -- i.e. every
    package here, since the fixture meta dicts are empty -- and the real
    run_for_package() requires meta["version"], which these fakes don't have).

    print_chroot_coverage/REQUIRE_CHROOT_COVERAGE default to "always covered" so
    callers that don't care about chroot-coverage gating (everything but
    TestCoprGatedByChrootCoverage) don't hit the real Copr API or leak the
    developer's actual REQUIRE_CHROOT_COVERAGE env var.

    Yields (copr_mock, forced_stages_spy) -- forced_stages_spy is None unless
    spy_forced_stages=True.
    """
    if is_cached_side_effect is None:

        def is_cached_side_effect(stage, pkg, target, new_hashes, forced_stages):
            # Only mock/copr are "not cached" -- exercises the real branches.
            return stage not in ("mock", "copr")

    with contextlib.ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(full_cycle, "compute_input_hashes", return_value={}))
        enter(patch.object(full_cycle, "effective_deps", return_value=set()))
        enter(patch.object(full_cycle, "is_cached", side_effect=is_cached_side_effect))
        enter(patch.object(full_cycle, "cache_miss_reason", return_value="test"))
        enter(patch.object(full_cycle.time, "sleep"))
        enter(patch.object(full_cycle._stage["stage-show-plan"], "show_plan"))
        enter(patch.object(full_cycle._stage["stage-validate"], "run_global_checks"))
        enter(
            patch.object(
                full_cycle._stage["stage-validate"],
                "run_for_package",
                return_value=True,
            )
        )
        enter(
            patch.object(
                full_cycle._stage["stage-vendor"], "run_for_package", return_value=True
            )
        )
        enter(
            patch.object(
                full_cycle._stage["stage-mock"],
                "run_for_package",
                side_effect=mock_side_effect,
            )
        )
        copr_mock = enter(
            patch.object(
                full_cycle._stage["stage-copr"], "run_for_package", return_value=True
            )
        )
        enter(patch.object(full_cycle, "poll_copr_status", return_value=False))
        enter(
            patch.object(full_cycle, "print_chroot_coverage", return_value=coverage_ok)
        )
        enter(
            patch.dict(
                os.environ,
                {"REQUIRE_CHROOT_COVERAGE": "true" if require_coverage else ""},
            )
        )

        forced_stages_spy = None
        if spy_forced_stages:
            forced_stages_spy = enter(
                patch.object(
                    full_cycle,
                    "compute_forced_stages",
                    wraps=full_cycle.compute_forced_stages,
                )
            )

        yield copr_mock, forced_stages_spy


class TestCoprGatedByMockFailure:
    """Regression coverage for issue #8 and docs/TODO.md TODO-0084.

    Per-package pipelines used to submit each package to Copr as soon as its
    own mock succeeded, so a healthy early package (hyprutils) could already be
    public by the time a later, dependent package (Hyprland) failed mock. The
    two-pass structure (mock every package, submit as a separate pass after)
    already prevents that, so Copr submission blocks only a failed package and
    its transitive dependents -- not the whole run (TODO-0084): an unrelated
    package, and a failed package's own already-published dependencies, still
    submit.

    Fixture graph for the transitive-scope tests:
    aquamarine <- Hyprland <- hyprland-plugins, plus unrelated mpvpaper.
    """

    def _run(
        self,
        packages,
        mock_outcomes,
        copr_repo="nett00n/hyprland",
        skip_copr=False,
        all_packages=None,
    ):
        """Run run_build_pipeline with heavy mocking; return (run_id, copr_mock).

        all_packages, if given, is what get_packages() (the full package set)
        returns -- lets a test model a PACKAGE=-filtered run where `packages`
        is a subset.
        """
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        def fake_mock_run_for_package(
            pkg,
            meta,
            fedora_version,
            target,
            proceed,
            mock_failed,
            all_pkgs,
            run_id_,
            repo_dir,
        ):
            ok = mock_outcomes[pkg]
            build_db.set_stage(
                pkg, "mock", target, run_id_, "success" if ok else "failed"
            )
            mock_failed[pkg] = not ok
            return ok

        with (
            patch.object(
                full_cycle, "get_packages", return_value=all_packages or packages
            ),
            _patched_pipeline(fake_mock_run_for_package) as (copr_mock, _),
        ):
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

    def test_unrelated_package_still_submitted(self):
        """The core TODO-0084 regression: mpvpaper has no relation to aquamarine
        and must reach Copr even though aquamarine's mock failed."""
        packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
            "mpvpaper": {},
        }
        run_id, copr_mock = self._run(
            packages,
            {"aquamarine": False, "Hyprland": True, "mpvpaper": True},
        )

        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert called_pkgs == {"mpvpaper"}

    def test_failed_package_itself_blocked(self):
        packages = {"aquamarine": {}, "mpvpaper": {}}
        run_id, copr_mock = self._run(packages, {"aquamarine": False, "mpvpaper": True})

        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert "aquamarine" not in called_pkgs
        entry = build_db.get_stage("aquamarine", "copr", TARGET)
        assert "blocked" in entry["reason"]
        assert "aquamarine" in entry["reason"]

    def test_direct_dependent_blocked(self):
        packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
        }
        run_id, copr_mock = self._run(packages, {"aquamarine": False, "Hyprland": True})

        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert "Hyprland" not in called_pkgs
        entry = build_db.get_stage("Hyprland", "copr", TARGET)
        assert "blocked" in entry["reason"]
        assert "aquamarine" in entry["reason"]

    def test_transitive_dependent_blocked(self):
        packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
            "hyprland-plugins": {"depends_on": ["Hyprland"]},
        }
        run_id, copr_mock = self._run(
            packages,
            {"aquamarine": False, "Hyprland": True, "hyprland-plugins": True},
        )

        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert "hyprland-plugins" not in called_pkgs
        entry = build_db.get_stage("hyprland-plugins", "copr", TARGET)
        assert "blocked" in entry["reason"]
        assert "aquamarine" in entry["reason"]

    def test_dependent_with_passing_mock_still_blocked(self):
        """Graph-membership-only rule: Hyprland's own mock succeeded, but it
        depends on the failed aquamarine, so it is blocked regardless."""
        packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
        }
        run_id, copr_mock = self._run(packages, {"aquamarine": False, "Hyprland": True})

        hyprland_mock = build_db.get_stage("Hyprland", "mock", TARGET)
        assert hyprland_mock["state"] == "success"
        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert "Hyprland" not in called_pkgs

    def test_dependency_of_failed_package_not_blocked(self):
        """aquamarine is Hyprland's dependency -- already published, unaffected
        by Hyprland's later mock failure -- so it must still submit."""
        packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
        }
        run_id, copr_mock = self._run(packages, {"aquamarine": True, "Hyprland": False})

        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert called_pkgs == {"aquamarine"}

    def test_all_mock_success_copr_runs_for_all(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id, copr_mock = self._run(packages, {"hyprutils": True, "Hyprland": True})

        assert copr_mock.call_count == 2
        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert called_pkgs == {"hyprutils", "Hyprland"}

    def test_package_filtered_run_dependent_outside_run_ignored(self):
        """PACKAGE=aquamarine: hyprland-plugins (a real dependent, but outside
        this run's package set) must not appear in the blocked map or crash."""
        all_packages = {
            "aquamarine": {},
            "Hyprland": {"depends_on": ["aquamarine"]},
            "hyprland-plugins": {"depends_on": ["Hyprland"]},
        }
        packages = {"aquamarine": {}}
        run_id, copr_mock = self._run(
            packages, {"aquamarine": False}, all_packages=all_packages
        )

        copr_mock.assert_not_called()
        entry = build_db.get_stage("aquamarine", "copr", TARGET)
        assert "blocked" in entry["reason"]
        assert build_db.get_stage("hyprland-plugins", "copr", TARGET) is None

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


class TestCoprInProgressNotResubmitted:
    """Regression coverage for docs/BUGS.md BUG-0002: a copr stage row still
    "unknown" (async submission, non-terminal) must not be resubmitted on the
    next run just because is_cached() can't treat "unknown" as a cache hit.
    """

    def _run(self, packages, mock_outcomes, is_cached_side_effect=None):
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        def fake_mock_run_for_package(
            pkg,
            meta,
            fedora_version,
            target,
            proceed,
            mock_failed,
            all_pkgs,
            run_id_,
            repo_dir,
        ):
            ok = mock_outcomes[pkg]
            build_db.set_stage(
                pkg, "mock", target, run_id_, "success" if ok else "failed"
            )
            mock_failed[pkg] = not ok
            return ok

        with (
            patch.object(full_cycle, "get_packages", return_value=packages),
            _patched_pipeline(
                fake_mock_run_for_package, is_cached_side_effect=is_cached_side_effect
            ) as (copr_mock, _),
        ):
            full_cycle.run_build_pipeline(
                packages,
                TARGET,
                run_id,
                fedora_version="44",
                copr_repo="nett00n/hyprland",
                proceed=False,
            )

        return run_id, copr_mock

    def test_still_unknown_after_poll_is_not_resubmitted(self):
        """A build left "unknown" (still non-terminal after poll_copr_status)
        must be left alone, not treated as a cache miss and resubmitted."""
        packages = {"hyprutils": {}}
        seed_run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(
            "hyprutils", "copr", TARGET, seed_run_id, "unknown", build_id=12345
        )

        # The harness's default is_cached_side_effect already says "not
        # cached" for copr here (matches real is_cached() behavior for a
        # non-"success" state) -- the in-progress short-circuit in
        # run_build_pipeline must catch it before that cache-miss path runs.
        run_id, copr_mock = self._run(packages, {"hyprutils": True})

        copr_mock.assert_not_called()
        entry = build_db.get_stage("hyprutils", "copr", TARGET)
        assert entry["reason"] == "in-progress"
        assert entry["state"] == "unknown"

    def test_unknown_without_build_id_still_resubmitted(self):
        """No build_id (e.g. submission itself never confirmed) means there's
        nothing to poll/track -- must fall through to a normal resubmission,
        not be treated as in-progress."""
        packages = {"hyprutils": {}}
        seed_run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("hyprutils", "copr", TARGET, seed_run_id, "unknown")

        run_id, copr_mock = self._run(packages, {"hyprutils": True})

        copr_mock.assert_called_once()

    def test_forced_stage_resubmits_even_if_prior_unknown(self):
        """A dependency-rebuild/force_run forcing the copr stage means a new
        version is in play -- the old in-flight build_id no longer matters,
        so this must still submit."""
        packages = {"hyprutils": {}}
        seed_run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(
            "hyprutils", "copr", TARGET, seed_run_id, "unknown", build_id=12345
        )

        with patch.object(full_cycle, "compute_forced_stages", return_value={"copr"}):
            run_id, copr_mock = self._run(packages, {"hyprutils": True})

        copr_mock.assert_called_once()


class TestResolveForcePackages:
    """Unit coverage for full_cycle.resolve_force_packages (FORCE_REBUILD scoping)."""

    def test_disabled_returns_empty_set(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        assert full_cycle.resolve_force_packages(False, "", packages) == set()
        assert full_cycle.resolve_force_packages(False, "Hyprland", packages) == set()

    def test_no_package_filter_forces_every_package_in_run(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        assert full_cycle.resolve_force_packages(True, "", packages) == set(packages)

    def test_package_filter_scopes_to_requested_only(self):
        """Deps pulled in transitively (present in `packages` but not requested) are excluded."""
        packages = {"hyprutils": {}, "Hyprland": {}}  # hyprutils pulled in as a dep
        result = full_cycle.resolve_force_packages(True, "Hyprland", packages)
        assert result == {"Hyprland"}

    def test_package_filter_ignores_names_not_in_run(self):
        packages = {"hyprutils": {}}
        result = full_cycle.resolve_force_packages(
            True, "Hyprland, hyprutils", packages
        )
        assert result == {"hyprutils"}


class TestForceRebuildOverridesProceed:
    """FORCE_REBUILD must force every stage for the affected package(s) and win over a
    PROCEED_BUILD resume for those same packages, while leaving untouched packages'
    PROCEED_BUILD behavior alone (see full-cycle.py's `pkg_proceed`).
    """

    def _run(self, force_packages):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        received_proceed: dict[str, bool] = {}

        def fake_mock_run_for_package(
            pkg,
            meta,
            fedora_version,
            target,
            proceed,
            mock_failed,
            all_pkgs,
            run_id_,
            repo_dir,
        ):
            received_proceed[pkg] = proceed
            build_db.set_stage(pkg, "mock", target, run_id_, "success")
            mock_failed[pkg] = False
            return True

        with (
            patch.object(full_cycle, "get_packages", return_value=packages),
            _patched_pipeline(fake_mock_run_for_package, spy_forced_stages=True) as (
                _,
                forced_stages_spy,
            ),
        ):
            full_cycle.run_build_pipeline(
                packages,
                TARGET,
                run_id,
                fedora_version="44",
                copr_repo="",
                proceed=True,
                force_packages=force_packages,
            )

        return received_proceed, forced_stages_spy

    def test_forced_package_gets_proceed_false_and_force_all_true(self):
        received_proceed, forced_stages_spy = self._run({"Hyprland"})

        assert received_proceed == {"hyprutils": True, "Hyprland": False}

        force_all_by_pkg = {
            call.args[0]: call.kwargs["force_all"]
            for call in forced_stages_spy.call_args_list
        }
        assert force_all_by_pkg["Hyprland"] is True
        assert force_all_by_pkg["hyprutils"] is False

    def test_no_force_packages_leaves_proceed_untouched(self):
        received_proceed, forced_stages_spy = self._run(set())

        assert received_proceed == {"hyprutils": True, "Hyprland": True}
        for call in forced_stages_spy.call_args_list:
            assert call.kwargs["force_all"] is False


class TestFullCyclePreflight:
    """Regression coverage for BUG-0036: full-cycle.py used to call
    check_copr_credentials() but discard the result, and never called
    validate_copr_repo() at all -- a bad COPR_REPO/token only failed after the
    full multi-hour build. main() must now fail fast, before any package work.
    """

    def test_bad_preflight_exits_before_any_package_work(self, monkeypatch):
        monkeypatch.setenv("COPR_REPO", "nett00n/hyprland")
        monkeypatch.delenv("SKIP_COPR", raising=False)

        with (
            patch.object(full_cycle, "preflight", return_value=False) as preflight_mock,
            patch.object(full_cycle, "prepare_packages") as prepare_packages_mock,
        ):
            with pytest.raises(SystemExit) as exc_info:
                full_cycle.main()

        preflight_mock.assert_called_once_with("nett00n/hyprland")
        assert exc_info.value.code == 2
        prepare_packages_mock.assert_not_called()

    def test_skip_copr_bypasses_preflight(self, monkeypatch):
        monkeypatch.setenv("COPR_REPO", "nett00n/hyprland")
        monkeypatch.setenv("SKIP_COPR", "true")

        with (
            patch.object(full_cycle, "preflight") as preflight_mock,
            patch.object(
                full_cycle, "prepare_packages", side_effect=SystemExit("stop-here")
            ),
        ):
            with pytest.raises(SystemExit):
                full_cycle.main()

        preflight_mock.assert_not_called()


class TestSkipReleaseBumpFlag:
    """full-cycle.py's own handling of SKIP_RELEASE_BUMP (docs/BUGS.md BUG-0049;
    the Makefile wiring that sets it per-chroot is covered by
    TestMatrixSkipsReleaseBumpOnNonCanonicalVersions above). update_package_releases()
    must run when the flag is unset, and must not run at all when it's true.
    """

    def _run_main(self, monkeypatch, skip_release_bump):
        monkeypatch.delenv("COPR_REPO", raising=False)
        monkeypatch.setenv("FEDORA_VERSION", "44")
        if skip_release_bump:
            monkeypatch.setenv("SKIP_RELEASE_BUMP", "true")
        else:
            monkeypatch.delenv("SKIP_RELEASE_BUMP", raising=False)

        with (
            patch.object(
                full_cycle, "prepare_packages", return_value={"hyprutils": {}}
            ),
            patch.object(full_cycle, "preflight_autoheal"),
            patch.object(full_cycle, "get_package_log_dir") as log_dir_mock,
            patch.object(full_cycle, "BUILD_LOG_DIR"),
            patch.object(full_cycle, "setup_run", return_value=1),
            patch.object(
                full_cycle, "update_package_releases", return_value={}
            ) as update_mock,
            patch.object(
                full_cycle,
                "resolve_force_packages",
                side_effect=SystemExit("stop-here"),
            ),
        ):
            log_dir_mock.return_value.exists.return_value = False
            with pytest.raises(SystemExit):
                full_cycle.main()

        return update_mock

    def test_skip_release_bump_true_skips_update_package_releases(self, monkeypatch):
        update_mock = self._run_main(monkeypatch, skip_release_bump=True)
        update_mock.assert_not_called()

    def test_skip_release_bump_unset_calls_update_package_releases(self, monkeypatch):
        update_mock = self._run_main(monkeypatch, skip_release_bump=False)
        update_mock.assert_called_once()


class TestCoprGatedByChrootCoverage:
    """Coverage for docs/BUGS.md BUG-0018's pre-submit gate: REQUIRE_CHROOT_COVERAGE=true
    must block Copr submission the same way a mock failure already does, while the
    default (unset) behavior only warns and still submits.
    """

    def _run(self, coverage_ok, require_coverage=False):
        packages = {"hyprutils": {}, "Hyprland": {}}
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")

        def fake_mock_run_for_package(
            pkg,
            meta,
            fedora_version,
            target,
            proceed,
            mock_failed,
            all_pkgs,
            run_id_,
            repo_dir,
        ):
            build_db.set_stage(pkg, "mock", target, run_id_, "success")
            mock_failed[pkg] = False
            return True

        with (
            patch.object(full_cycle, "get_packages", return_value=packages),
            _patched_pipeline(
                fake_mock_run_for_package,
                coverage_ok=coverage_ok,
                require_coverage=require_coverage,
            ) as (copr_mock, _),
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
    docs/BUGS.md BUG-0018: it must loop per-version full-cycle with SKIP_COPR=true,
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


class TestMatrixNoEarlyAbort:
    """Coverage for the matrix's failure-tolerant rework (docs/BUGS.md
    BUG-0053): a failing chroot must not stop the rest of the matrix, nor
    skip Copr submission for packages that built cleanly elsewhere. `make -k`
    plus an order-only prerequisite on the canonical chroot looked like it
    gave this for free, but GNU Make's `-k` explicitly refuses to attempt a
    goal whose (even order-only) prerequisite failed -- reproduced in
    isolation and confirmed live: for as long as any package failed on the
    canonical chroot, matrix-chroot-44/45 were silently never attempted at
    all, night after night, blocking every package's Copr submission
    regardless of relation to the actual failure. Fixed by replacing Make's
    own scheduling with a plain shell loop (`for v in $(MATRIX_ORDERED_VERSIONS)`)
    that always continues to the next chroot.

    Confirmed for real (not just this dry-run text) by running `make
    full-cycle-matrix PACKAGE=hyprutils CANONICAL_FEDORA_VERSION=99
    MATRIX_VERSIONS="99 43 44" COPR_REPO=`: fedora-99 fails fast (unsupported
    FEDORA_VERSION), 43 and 44 both still complete ("Full cycle completed"
    for each, real `runs` rows recorded), the "COPR_REPO not set" branch is
    still reached afterward, and the overall exit code is nonzero -- exactly
    the shape these dry-run assertions check without needing a container. The
    same command against the pre-fix Makefile reproduces the bug verbatim:
    "Target 'matrix-chroot-43' not remade because of errors." / "Target
    'matrix-chroot-44' not remade because of errors."
    """

    def test_loop_no_longer_contains_early_abort(self):
        result = subprocess.run(
            ["make", "-n", "full-cycle-matrix", "MATRIX_VERSIONS=43 44", "COPR_REPO="],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # `|| exit 1` legitimately appears elsewhere in the dry-run text (the
        # PIPELINE_LOCK_HELD guard, container-build's own error handling) --
        # what must be gone specifically is the old per-version abort on the
        # `$(MAKE) full-cycle ...` call itself.
        for line in result.stdout.splitlines():
            if "make full-cycle FEDORA_VERSION=" in line or line.strip().startswith(
                "SKIP_RELEASE_BUMP="
            ):
                assert "|| exit 1" not in line
        assert "for v in 43 44; do" in result.stdout
        assert "overall=0; failed_chroots=" in result.stdout

    def test_loops_over_matrix_chroot_targets_without_dash_k(self):
        result = subprocess.run(
            ["make", "-n", "full-cycle-matrix", "MATRIX_VERSIONS=43 44", "COPR_REPO="],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # `-k` refuses to attempt a goal whose (even order-only) prerequisite
        # failed -- exactly the mechanism that starved fedora-44/45 (BUG-0053)
        # -- so it must be gone entirely from the matrix loop.
        assert "make -k" not in result.stdout
        assert "make matrix-chroot-$v" in result.stdout

    def test_canonical_chroot_is_ordered_before_others_regardless_of_list_order(self):
        """The canonical chroot performs the release bump (BUG-0049), so every
        other chroot must build after it even if MATRIX_VERSIONS lists it
        last -- MATRIX_ORDERED_VERSIONS ($(filter)/$(filter-out) on
        CANONICAL_FEDORA_VERSION), not raw list order, must enforce this. This
        replaced an order-only Make prerequisite that enforced the same
        ordering but, combined with `make -k`, silently starved every
        non-canonical chroot whenever the canonical one failed (BUG-0053)."""
        result = subprocess.run(
            [
                "make",
                "-n",
                "full-cycle-matrix",
                "MATRIX_VERSIONS=45 44 43",
                "COPR_REPO=",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        order = re.findall(r'"Fedora (\d+)"', result.stdout)
        assert order == ["43", "45", "44"]

    def test_stage_copr_call_is_not_conditioned_on_matrix_success(self):
        """The `if -n "$(COPR_REPO)"` branch must be reached unconditionally --
        not gated behind the matrix loop's own exit status -- so packages that
        built cleanly are still submitted even if another chroot failed."""
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
        matrix_call_pos = result.stdout.index("make matrix-chroot-$v")
        status_capture_pos = result.stdout.index("overall=0; failed_chroots=")
        copr_call_pos = result.stdout.index("make stage-copr")
        exit_pos = result.stdout.rindex("exit $overall")
        assert status_capture_pos < matrix_call_pos < copr_call_pos < exit_pos
        # stage-copr's own exit status must now be folded into `overall` too
        # (docs/BUGS.md BUG-0050 -- it used to be silently discarded, so a
        # failed Copr submission was invisible to update-daily's own gate).
        copr_line = next(
            line
            for line in result.stdout.splitlines()
            if "REQUIRE_CHROOT_COVERAGE=" in line and "make stage-copr" not in line
        )
        assert "|| overall=1" in copr_line


class TestMatrixSkipsReleaseBumpOnNonCanonicalVersions:
    """Coverage for docs/BUGS.md BUG-0049: update_package_releases() reads its
    rebuild signal from the *spec* stage's row for the run's own `target`
    (lib.yaml_utils.py), so a matrix run that called it once per chroot would
    bump a package's release once per chroot too -- up to 3x in one nightly,
    each rewriting the shared packages.yaml. full-cycle-matrix now sets
    SKIP_RELEASE_BUMP=true for every chroot except CANONICAL_FEDORA_VERSION,
    so full-cycle.py's pre-build release step runs exactly once per matrix run
    regardless of how many chroots are in MATRIX_VERSIONS.
    """

    def test_canonical_version_does_not_skip_release_bump(self):
        result = subprocess.run(
            [
                "make",
                "-n",
                "full-cycle-matrix",
                "MATRIX_VERSIONS=43 44 45",
                "COPR_REPO=",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        lines = [
            line
            for line in result.stdout.splitlines()
            if "scripts/full-cycle.py" in line
        ]
        assert len(lines) == 3
        canonical_line = next(line for line in lines if "FEDORA_VERSION=43 " in line)
        non_canonical_lines = [
            line for line in lines if "FEDORA_VERSION=43 " not in line
        ]
        assert len(non_canonical_lines) == 2
        assert "SKIP_RELEASE_BUMP= " in canonical_line
        for line in non_canonical_lines:
            assert "SKIP_RELEASE_BUMP=true" in line

    def test_matrix_versions_without_canonical_skips_bump_everywhere(self):
        """Documented edge case: if MATRIX_VERSIONS excludes the canonical
        version entirely, no invocation runs the release bump this run --
        picking an arbitrary substitute would be more surprising than simply
        not bumping."""
        result = subprocess.run(
            ["make", "-n", "full-cycle-matrix", "MATRIX_VERSIONS=44 45", "COPR_REPO="],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        lines = [
            line
            for line in result.stdout.splitlines()
            if "scripts/full-cycle.py" in line
        ]
        assert len(lines) == 2
        for line in lines:
            assert "SKIP_RELEASE_BUMP=true" in line


class TestSkipPackagesForceRebuildForwarding:
    """Coverage for docs/BUGS.md BUG-0046: full-cycle-matrix's per-version loop
    didn't forward SKIP_PACKAGES/FORCE_REBUILD to its nested full-cycle calls, and
    full-cycle's own container recipe never forwarded SKIP_PACKAGES into the script
    env at all (only FORCE_REBUILD was present there) -- so even a plain `make
    full-cycle SKIP_PACKAGES=x` silently dropped it.
    """

    def test_full_cycle_forwards_skip_packages_into_script_env(self):
        result = subprocess.run(
            ["make", "-n", "full-cycle", "SKIP_PACKAGES=foo,bar", "COPR_REPO="],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "SKIP_PACKAGES=foo,bar" in result.stdout
        # Must reach the actual script invocation, not just be echoed somewhere.
        script_pos = result.stdout.index("scripts/full-cycle.py")
        skip_pos = result.stdout.rindex("SKIP_PACKAGES=foo,bar")
        assert skip_pos < script_pos

    def test_full_cycle_matrix_forwards_both_vars_to_nested_full_cycle(self):
        result = subprocess.run(
            [
                "make",
                "-n",
                "full-cycle-matrix",
                "SKIP_PACKAGES=foo",
                "FORCE_REBUILD=1",
                "MATRIX_VERSIONS=43",
                "COPR_REPO=",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # The matrix is now real matrix-chroot-% targets, not a shell `for`
        # loop -- both vars must reach the nested full-cycle call each one
        # makes.
        chroot_pos = result.stdout.index("make full-cycle FEDORA_VERSION=43")
        assert "SKIP_PACKAGES=foo" in result.stdout[chroot_pos:]
        assert "FORCE_REBUILD=1" in result.stdout[chroot_pos:]


class TestPackageVarSemantics:
    """Coverage for docs/TODO.md TODO-0029: PACKAGE meant three different things across
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
        for value, expected in [
            ("", "NO_MATCH"),
            ("hyprutils", "NO_MATCH"),
            ("a,b", "MATCHED"),
        ]:
            result = subprocess.run(
                ["sh", "-c", guard.format(value)], capture_output=True, text=True
            )
            assert result.stdout.strip() == expected, f"PACKAGE={value!r}"

    def test_gather_requires_uses_rpm_var(self):
        rpm = "local-repo/fedora-44-x86_64/hyprutils-0.14.0.fc44.x86_64.rpm"
        result = subprocess.run(
            ["make", "-n", "gather-requires", f"RPM={rpm}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert f"gather-requires.py {rpm}" in result.stdout
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


class TestSingleContainerTargets:
    """`sources`/`stage-log-analyze`/`readme` used to spawn one podman container per
    package (or per template, for readme) via a shell/Makefile loop. They now spawn
    one container for the whole package list. Asserted via `make -n` dry-run text
    (following TestPackageVarSemantics.test_pkgs_expands_comma_list_to_space_separated
    above) rather than actually invoking podman, which these unit tests don't have.
    """

    def _dry_run(self, *args: str) -> str:
        result = subprocess.run(
            ["make", "-n", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    def test_sources_uses_one_container_for_the_whole_package_list(self):
        stdout = self._dry_run("sources", "PACKAGE=a,b")
        # One podman invocation for spectool (a second, separate one is expected for
        # the check-checksums sub-make sources already chains to).
        assert stdout.count("spectool -g -R") == 1
        # Both packages' downloads happen inside that one container's shell for-loop
        # ("sh -c '... for pkg in a b ... spectool ...'"), not as two separate
        # `podman run` invocations -- the recipe line wraps with a trailing `\`, so
        # match across the joined block rather than a single physical line.
        assert "sh -c 'set -e; for pkg in a b; do" in stdout
        block_start = stdout.index("sh -c 'set -e; for pkg in a b; do")
        block_end = stdout.index("done'", block_start)
        assert "spectool -g -R" in stdout[block_start:block_end]

    def test_stage_log_analyze_uses_one_container_for_the_whole_package_list(self):
        stdout = self._dry_run("stage-log-analyze", "PACKAGE=a,b")
        assert stdout.count("pkg-log-analysis.py") == 1
        analyze_line = next(
            line for line in stdout.splitlines() if "pkg-log-analysis.py" in line
        )
        assert analyze_line.rstrip().endswith("pkg-log-analysis.py a b")

    def test_stage_log_analyze_respects_skip_packages(self):
        stdout = self._dry_run("stage-log-analyze", "PACKAGE=a,b,c", "SKIP_PACKAGES=b")
        analyze_line = next(
            line for line in stdout.splitlines() if "pkg-log-analysis.py" in line
        )
        assert analyze_line.rstrip().endswith("pkg-log-analysis.py a c")

    def test_readme_renders_all_three_formats_from_one_container(self):
        stdout = self._dry_run("readme")
        assert stdout.count("gen-report.py") == 1
        assert stdout.count("podman run --rm --privileged") == 1
        block_start = stdout.index("gen-report.py")
        block_end = stdout.index("2>", block_start)
        render_block = stdout[block_start:block_end]
        assert "--format github" in render_block
        assert "--format copr" in render_block
        assert "--format full-report" in render_block
        assert "--output ./README.md" in render_block
        assert "--output ./docs/README.copr.md" in render_block
        assert "--output ./docs/full-report.md" in render_block
        # The old per-template --skip-copr-poll is gone -- one shared poll now covers
        # all three renders.
        assert "--skip-copr-poll" not in render_block


class TestMockChrootForwarding:
    """docs/BUGS.md BUG-0019: stage-spec/stage-vendor/stage-srpm/stage-copr didn't
    forward MOCK_CHROOT into the container (stage-mock did), so a MOCK_CHROOT
    override resolved a different `target` on those stages than on stage-mock --
    and stage-vendor separately dropped SKIP_PACKAGES even though it reads it via
    prepare_stage(). Asserted via `make -n` dry-run text, same approach as
    TestSingleContainerTargets above.
    """

    def _dry_run(self, *args: str) -> str:
        result = subprocess.run(
            ["make", "-n", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    @pytest.mark.parametrize(
        "target,script",
        [
            ("stage-spec", "scripts/stage-spec.py"),
            ("stage-vendor", "scripts/stage-vendor.py"),
            ("stage-srpm", "scripts/stage-srpm.py"),
            ("stage-copr", "scripts/stage-copr.py"),
        ],
    )
    def test_forwards_mock_chroot_override(self, target, script):
        extra = ["COPR_REPO=nett00n/hyprland"] if target == "stage-copr" else []
        stdout = self._dry_run(target, "MOCK_CHROOT=fedora-rawhide-x86_64", *extra)
        line = next(line for line in stdout.splitlines() if script in line)
        assert "MOCK_CHROOT=fedora-rawhide-x86_64" in line

    def test_stage_vendor_forwards_skip_packages(self):
        stdout = self._dry_run("stage-vendor", "SKIP_PACKAGES=foo")
        line = next(
            line for line in stdout.splitlines() if "scripts/stage-vendor.py" in line
        )
        assert "SKIP_PACKAGES=foo" in line


class TestProceedBuildForwarding:
    """docs/BUGS.md BUG-0016: the standalone stage-* targets never forwarded
    PROCEED_BUILD into the container's env allowlist the way _full-cycle does
    (Makefile:549) -- so `make stage-mock PACKAGE=X PROCEED_BUILD=true` ran in
    non-proceed mode and lib.yaml_utils.prepare_stage() cleared the very rows
    the operator opted out of clearing (docs/operations.md "Rules"). Asserted
    via `make -n` dry-run text, same approach as TestMockChrootForwarding
    above.
    """

    def _dry_run(self, *args: str) -> str:
        result = subprocess.run(
            ["make", "-n", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    @pytest.mark.parametrize(
        "target,script",
        [
            ("stage-validate", "scripts/stage-validate.py"),
            ("stage-spec", "scripts/stage-spec.py"),
            ("stage-vendor", "scripts/stage-vendor.py"),
            ("stage-srpm", "scripts/stage-srpm.py"),
            ("stage-mock", "scripts/stage-mock.py"),
            ("stage-copr", "scripts/stage-copr.py"),
        ],
    )
    def test_forwards_proceed_build(self, target, script):
        extra = ["COPR_REPO=nett00n/hyprland"] if target == "stage-copr" else []
        stdout = self._dry_run(target, "PROCEED_BUILD=true", *extra)
        line = next(line for line in stdout.splitlines() if script in line)
        assert "PROCEED_BUILD=true" in line

    def test_unset_proceed_build_is_not_truthy(self):
        stdout = self._dry_run("stage-mock")
        line = next(
            line for line in stdout.splitlines() if "scripts/stage-mock.py" in line
        )
        assert "PROCEED_BUILD=true" not in line
        assert "PROCEED_BUILD=" in line


class TestMockCacheVolumes:
    """TODO-0014: mock's buildroot cache now persists across --rm containers via
    named volumes instead of being rebuilt from scratch on every run."""

    def _dry_run(self, *args: str) -> str:
        result = subprocess.run(
            ["make", "-n", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    def test_stage_mock_mounts_cache_and_root_volumes(self):
        stdout = self._dry_run("stage-mock", "PACKAGE=x", "FEDORA_VERSION=44")
        assert "mock-cache-44:/var/cache/mock:z" in stdout
        assert "mock-root-44:/var/lib/mock:z" in stdout

    def test_volumes_are_per_fedora_version(self):
        stdout = self._dry_run("stage-mock", "PACKAGE=x", "FEDORA_VERSION=43")
        assert "mock-cache-43:/var/cache/mock:z" in stdout
        assert "mock-root-43:/var/lib/mock:z" in stdout
        assert "mock-cache-44" not in stdout

    def test_clean_mock_cache_removes_both_volumes(self):
        stdout = self._dry_run("clean-mock-cache", "FEDORA_VERSION=44")
        assert "volume rm mock-cache-44" in stdout
        assert "volume rm mock-root-44" in stdout

    def test_clean_localrepo_also_drops_mock_cache(self):
        """A stale local-repo can poison the persisted dnf cache too (docs/TODO.md
        TODO-0014's stated worry) -- the two must be reset together."""
        stdout = self._dry_run("clean-localrepo", "FEDORA_VERSION=44")
        assert "volume rm mock-cache-44" in stdout
        assert "volume rm mock-root-44" in stdout
        # local-repo is a plain directory now (docs/CHANGELOG.md 2026-08-11), not a podman
        # volume -- clean-localrepo must purge local-repo/<target>/ and its ledger rows,
        # not (any longer) reach for a volume at all.
        assert "volume rm local-repo-44" not in stdout
        assert "rm -rf local-repo/fedora-44-x86_64" in stdout
        assert "--forget-repo fedora-44-x86_64" in stdout

    def test_container_volume_clean_removes_mock_volumes_too(self):
        stdout = self._dry_run(
            "container-volume-clean", "FEDORA_VERSION=44", "RECURSIVE_CALL=1"
        )
        assert "volume rm mock-cache-44" in stdout
        assert "volume rm mock-root-44" in stdout

    def test_container_volume_clean_keeps_legacy_localrepo_volume_sweep(self):
        """local-repo-<ver> is no longer created (local-repo is a plain per-target
        directory now), but a guarded `volume rm` for it stays for one cycle so
        machines with the old volume still get cleaned up."""
        stdout = self._dry_run(
            "container-volume-clean", "FEDORA_VERSION=44", "RECURSIVE_CALL=1"
        )
        assert "volume rm local-repo-44" in stdout

    def test_setup_volumes_no_longer_creates_localrepo_volume(self):
        stdout = self._dry_run("setup-volumes", "FEDORA_VERSION=44")
        assert "volume create local-repo-44" not in stdout
        assert "mkdir -p local-repo/fedora-44-x86_64" in stdout


class TestUpdateDailyResilience:
    """Coverage for docs/TODO.md TODO-0061 (a failed package build must not abort readme/
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
        assert "make full-cycle-matrix || touch logs/.update-daily-failed" in stdout
        # readme/copr-description and the git commit block must appear AFTER the
        # full-cycle-matrix line, i.e. not gated behind its success.
        full_cycle_pos = stdout.index("make full-cycle-matrix || touch")
        readme_pos = stdout.index("make readme copr-description")
        commit_pos = stdout.index('git commit -m "Daily update:')
        marker_check_pos = stdout.index("if [ -f logs/.update-daily-failed ]")
        assert full_cycle_pos < readme_pos < commit_pos < marker_check_pos

    def test_stale_marker_cleared_at_start(self):
        stdout = self._dry_run()
        assert "mkdir -p logs && rm -f logs/.update-daily-failed" in stdout

    def test_packages_yaml_revalidated_after_release_bump_before_docs(self):
        """Coverage for docs/BUGS.md BUG-0044: full-cycle.py's update_package_releases()
        rewrites packages.yaml (release bumps/resets) *after* the pre-build
        validate-packages+fmt gate has already run, so the file that gets committed
        and rendered into the docs was never re-checked. A second, fmt-less
        `validate-packages` must run between full-cycle and readme/copr-description --
        no re-fmt, since the rewrite already goes through the same formatter
        (write_yaml_file's FORMAT_FILE) that `make fmt` itself uses.
        """
        stdout = self._dry_run()
        # Exactly one "...fmt" gate: the pre-build one. The post-build gate is
        # validate-packages alone.
        assert stdout.count("make validate-packages fmt") == 1
        full_cycle_pos = stdout.index("make full-cycle-matrix || touch")
        readme_pos = stdout.index("make readme copr-description")
        second_validate_pos = stdout.index("make validate-packages", full_cycle_pos)
        assert full_cycle_pos < second_validate_pos < readme_pos
        # And it must be the bare form, not another "... fmt" line.
        line_end = stdout.index("\n", second_validate_pos)
        assert "fmt" not in stdout[second_validate_pos:line_end]

    def test_stage_log_analyze_runs_after_readme_before_commit(self):
        """Coverage for docs/BUGS.md BUG-0041: full-cycle.py's next run rmtree's
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


class TestDevToolingPrerequisite:
    """Coverage for docs/BUGS.md BUG-0032: requirements-dev.txt (ruff/mypy/flake8/yamllint/
    rpmlint/pytest-cov) used to be installed only as a side effect of `lint-flake`'s recipe,
    which runs *after* `lint-ruff` in the `lint` target's prerequisite list -- so a fresh
    `.venv` (post `make setup-venv`, which installs only requirements.txt) died at `lint-ruff`
    with "ruff: command not found". `install-dev` is now a shared prerequisite of every
    lint/fmt/coverage target, verified here via `make -n` dry-run text so the ordering
    regression can't silently come back.
    """

    def _dry_run(self, *args: str) -> str:
        result = subprocess.run(
            ["make", "-n", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        return result.stdout

    def test_lint_installs_dev_deps_before_ruff_check(self):
        stdout = self._dry_run("lint", "NO_CONTAINER=1")
        assert "requirements-dev.txt" in stdout
        install_pos = stdout.index("requirements-dev.txt")
        ruff_pos = stdout.index("ruff check")
        assert install_pos < ruff_pos

    def test_lint_installs_dev_deps_exactly_once(self):
        stdout = self._dry_run("lint", "NO_CONTAINER=1")
        assert stdout.count("requirements-dev.txt") == 1

    def test_fmt_installs_dev_deps(self):
        stdout = self._dry_run("fmt", "NO_CONTAINER=1")
        assert "requirements-dev.txt" in stdout

    def test_coverage_installs_dev_deps(self):
        stdout = self._dry_run("coverage", "NO_CONTAINER=1")
        assert "requirements-dev.txt" in stdout

    def test_update_daily_does_not_install_dev_deps(self):
        """The nightly gate is validate-packages+fmt only (TODO-0064) -- fmt needs dev
        tooling for fmt-ruff, but plain `test` (not part of update-daily) must not."""
        stdout = self._dry_run(
            "update-daily", "COPR_REPO=nett00n/hyprland", "NO_CONTAINER=1"
        )
        assert "requirements-dev.txt" in stdout  # via fmt's fmt-ruff dependency
        assert "pytest tests/" not in stdout


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


class TestPipelineLock:
    """Coverage for docs/BUGS.md BUG-0043: update-daily/full-cycle/full-cycle-matrix
    share a non-blocking flock (default path logs/.pipeline.lock, overridden here to
    a tmp_path file via PIPELINE_LOCK_FILE= so tests never touch real repo state) so
    two overlapping runs (e.g. a slow nightly cron job still going when the next one
    fires) refuse instead of corrupting build-report.db, the mock/rpmbuild podman
    volumes, or the git index.

    Note on `make -n` here: GNU make still runs a recipe line for real under -n if
    the line's raw, as-written text contains "$(MAKE)" (see full-cycle-matrix's own
    `for`-loop and TestFullCycleMatrixTarget's comment) -- our guard lines qualify,
    so `flock` really runs and really succeeds/fails even under -n. But -n *also*
    prints the recipe's raw template text regardless of which branch executes, so
    the string "already in progress" always appears once from that static dump.
    A REAL refusal additionally executes the `echo` in the failing branch, printing
    it a second time -- so the signal is an occurrence *count*, not presence, paired
    with whether recursion actually reached a downstream target (here: check-venv's
    "test -x .venv/bin/python3" line, which only prints if `_full-cycle` was truly
    reached -- chosen over check-image's own line since that one differs under
    NO_CONTAINER=1, which the surrounding test run may or may not have set).
    """

    def _lock_file(self, tmp_path) -> Path:
        return tmp_path / "pipeline.lock"

    def _dry_run(self, target: str, lock_file: Path, *extra_args: str):
        return subprocess.run(
            ["make", "-n", target, f"PIPELINE_LOCK_FILE={lock_file}", *extra_args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_update_daily_dry_run_takes_lock_then_recurses(self, tmp_path):
        result = self._dry_run(
            "update-daily", self._lock_file(tmp_path), "COPR_REPO=nett00n/hyprland"
        )

        assert result.returncode == 0
        assert "flock" in result.stdout
        assert "PIPELINE_LOCK_HELD=1" in result.stdout
        # Real recursion into _update-daily reached its own recipe body.
        assert "rm -f logs/.update-daily-failed" in result.stdout

    def test_second_run_refuses_while_lock_held(self, tmp_path):
        lock_file = self._lock_file(tmp_path)
        with open(lock_file, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

            result = subprocess.run(
                [
                    "make",
                    "full-cycle",
                    f"PIPELINE_LOCK_FILE={lock_file}",
                    "COPR_REPO=nett00n/hyprland",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env={**os.environ, "NO_CONTAINER": "1"},
            )

            assert result.returncode != 0
            assert "already in progress" in result.stdout
            # The lock check must fire before any real build work -- full-cycle.py
            # is never reached.
            assert "full-cycle.py" not in result.stdout

    def test_lock_released_after_holder_exits(self, tmp_path):
        lock_file = self._lock_file(tmp_path)
        with open(lock_file, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # `held` is closed now -- the flock releases with it, same as a crashed or
        # finished holder process. A fresh attempt must succeed, not see a stale lock.

        result = self._dry_run("full-cycle", lock_file, "COPR_REPO=nett00n/hyprland")

        assert result.returncode == 0
        # Static template text only (never really executed) -- one occurrence.
        assert result.stdout.count("already in progress") == 1
        # Real recursion into _full-cycle reached check-image's recipe.
        assert "test -x .venv/bin/python3" in result.stdout

    def test_full_cycle_matrix_inner_full_cycle_does_not_relock(self, tmp_path):
        lock_file = self._lock_file(tmp_path)
        result = self._dry_run(
            "full-cycle-matrix", lock_file, "MATRIX_VERSIONS=43", "COPR_REPO="
        )

        assert result.returncode == 0
        # The outer full-cycle-matrix takes the lock for real once; its nested
        # `make full-cycle` (from the version loop, itself force-run under -n)
        # must inherit PIPELINE_LOCK_HELD=1 and skip straight past its own guard
        # instead of trying to flock a file it's already holding. Two static
        # template occurrences are expected here (one from full-cycle-matrix's own
        # guard, one from full-cycle's) -- a real self-refusal would add a THIRD,
        # really-executed echo and suppress the downstream check-venv recursion,
        # exactly like test_second_run_refuses.
        assert result.stdout.count("already in progress") == 2
        assert "test -x .venv/bin/python3" in result.stdout

    def test_lock_disable_bypasses_guard_even_when_lock_held(self, tmp_path):
        lock_file = self._lock_file(tmp_path)
        with open(lock_file, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

            result = self._dry_run(
                "full-cycle",
                lock_file,
                "COPR_REPO=nett00n/hyprland",
                "LOCK_DISABLE=1",
            )

        assert result.returncode == 0
        assert result.stdout.count("already in progress") == 1
        assert "test -x .venv/bin/python3" in result.stdout

    def test_pipeline_lock_held_bypasses_guard_even_when_lock_held(self, tmp_path):
        lock_file = self._lock_file(tmp_path)
        with open(lock_file, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

            result = self._dry_run(
                "full-cycle",
                lock_file,
                "COPR_REPO=nett00n/hyprland",
                "PIPELINE_LOCK_HELD=1",
            )

        assert result.returncode == 0
        assert result.stdout.count("already in progress") == 1
        assert "test -x .venv/bin/python3" in result.stdout
