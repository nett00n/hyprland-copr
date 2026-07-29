"""Integration tests for make targets and pipeline components."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import logging

import pytest

# Import using importlib to handle module names with dashes
import importlib

full_cycle = importlib.import_module("scripts.full-cycle")
stage_copr = importlib.import_module("scripts.stage-copr")
stage_vendor = importlib.import_module("scripts.stage-vendor")
stage_srpm = importlib.import_module("scripts.stage-srpm")
stage_mock = importlib.import_module("scripts.stage-mock")
stage_show_plan = importlib.import_module("scripts.stage-show-plan")

ROOT = Path(__file__).parent.parent.parent


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
        build_status = {
            "run": {"timestamp": "2025-01-01T00:00:00+00:00"},
            "stages": {
                "spec": {
                    "pkg1": {"state": "success"},
                    "pkg2": {"state": "success"},
                },
                "copr": {
                    "pkg1": {"state": "unknown"},  # valid in async mode
                    "pkg2": {"state": "unknown"},
                },
            },
        }

        with patch.object(full_cycle, "load_build_status") as mock_load, \
             patch.object(full_cycle, "print_summary"), \
             patch.object(full_cycle, "dump_yaml_pretty"), \
             patch.object(full_cycle, "report_mock_failures"):
            mock_load.return_value = build_status

            with patch.object(Path, "write_text"):
                # Should not raise SystemExit
                full_cycle.finalize_report(
                    packages, build_status, "", synchronous_copr=False
                )

    def test_sync_copr_failed_is_failure(self):
        """When SYNCHRONOUS_COPR_BUILD=true, 'failed' COPR state is failure."""
        packages = {"pkg1": {}}
        build_status = {
            "run": {"timestamp": "2025-01-01T00:00:00+00:00"},
            "stages": {
                "copr": {
                    "pkg1": {"state": "failed"},  # failure in sync mode
                },
            },
        }

        with patch.object(full_cycle, "load_build_status") as mock_load, \
             patch.object(full_cycle, "print_summary"), \
             patch.object(full_cycle, "dump_yaml_pretty"), \
             patch.object(full_cycle, "report_mock_failures"), \
             pytest.raises(SystemExit) as exc:
            mock_load.return_value = build_status

            with patch.object(Path, "write_text"):
                full_cycle.finalize_report(
                    packages, build_status, "", synchronous_copr=True
                )

        assert exc.value.code == 1

    def test_non_copr_failed_always_fails(self):
        """Failed spec/srpm/mock stage always fails, regardless of sync setting."""
        packages = {"pkg1": {}}
        build_status = {
            "run": {"timestamp": "2025-01-01T00:00:00+00:00"},
            "stages": {
                "spec": {
                    "pkg1": {"state": "failed"},
                },
            },
        }

        with patch.object(full_cycle, "load_build_status") as mock_load, \
             patch.object(full_cycle, "print_summary"), \
             patch.object(full_cycle, "dump_yaml_pretty"), \
             patch.object(full_cycle, "report_mock_failures"), \
             pytest.raises(SystemExit) as exc:
            mock_load.return_value = build_status

            with patch.object(Path, "write_text"):
                full_cycle.finalize_report(
                    packages, build_status, "", synchronous_copr=False
                )

        assert exc.value.code == 1

    def test_validation_failure_ignored(self):
        """Validation stage failures do not cause pipeline failure."""
        packages = {"pkg1": {}}
        build_status = {
            "run": {"timestamp": "2025-01-01T00:00:00+00:00"},
            "stages": {
                "validate": {
                    "pkg1": {"state": "failed"},  # validation fails
                },
                "spec": {
                    "pkg1": {"state": "success"},
                },
            },
        }

        with patch.object(full_cycle, "load_build_status") as mock_load, \
             patch.object(full_cycle, "print_summary"), \
             patch.object(full_cycle, "dump_yaml_pretty"), \
             patch.object(full_cycle, "report_mock_failures"):
            mock_load.return_value = build_status

            with patch.object(Path, "write_text"):
                # Should not raise SystemExit
                full_cycle.finalize_report(
                    packages, build_status, "", synchronous_copr=False
                )


class TestMockFailedPackages:
    """Test mock_failed_packages(), the pure helper behind the Copr gate."""

    def test_no_failures(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        build_status = {
            "stages": {
                "mock": {
                    "hyprutils": {"state": "success"},
                    "Hyprland": {"state": "success"},
                }
            }
        }
        assert full_cycle.mock_failed_packages(packages, build_status) == []

    def test_one_failure(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        build_status = {
            "stages": {
                "mock": {
                    "hyprutils": {"state": "success"},
                    "Hyprland": {"state": "failed"},
                }
            }
        }
        assert full_cycle.mock_failed_packages(packages, build_status) == ["Hyprland"]

    def test_missing_entry_not_a_failure(self):
        """A package with no mock entry at all (e.g. skipped) isn't a 'failure'."""
        packages = {"pkg1": {}}
        build_status = {"stages": {"mock": {}}}
        assert full_cycle.mock_failed_packages(packages, build_status) == []

    def test_only_considers_packages_in_this_run(self):
        """A failure recorded for a package outside this run's set doesn't count."""
        packages = {"hyprutils": {}}
        build_status = {
            "stages": {
                "mock": {
                    "hyprutils": {"state": "success"},
                    "some-other-pkg": {"state": "failed"},
                }
            }
        }
        assert full_cycle.mock_failed_packages(packages, build_status) == []


class TestCoprGatedByMockFailure:
    """Regression coverage for issue #8: per-package pipelines used to submit
    each package to Copr as soon as its own mock succeeded, so a healthy early
    package (hyprutils) could already be public by the time a later, dependent
    package (Hyprland) failed mock. Copr submission must now be an all-or-nothing
    pass gated on every package's mock having succeeded this run.
    """

    def _base_build_status(self):
        return {
            "stages": {s: {} for s in ["validate", "spec", "vendor", "srpm", "mock", "copr"]}
        }

    def _run(self, packages, mock_outcomes, copr_repo="nett00n/hyprland"):
        """Run run_build_pipeline with heavy mocking; return (build_status, copr_mock)."""
        build_status = self._base_build_status()

        def fake_mock_run_for_package(
            pkg, meta, build_status, fedora_version, mock_chroot_name,
            proceed, mock_failed, all_pkgs,
        ):
            ok = mock_outcomes[pkg]
            build_status["stages"]["mock"][pkg] = {
                "state": "success" if ok else "failed"
            }
            mock_failed[pkg] = not ok
            return ok

        def fake_is_cached(stage, pkg, build_status, new_hashes, forced_stages):
            # Only mock/copr are "not cached" -- exercises the real branches.
            return stage not in ("mock", "copr")

        with patch.object(full_cycle, "get_packages", return_value=packages), \
             patch.object(full_cycle, "compute_input_hashes", return_value={}), \
             patch.object(full_cycle, "effective_deps", return_value=set()), \
             patch.object(full_cycle, "is_cached", side_effect=fake_is_cached), \
             patch.object(full_cycle, "cache_miss_reason", return_value="test"), \
             patch.object(full_cycle, "save_build_status"), \
             patch.object(full_cycle.time, "sleep"), \
             patch.object(full_cycle._stage["stage-show-plan"], "show_plan"), \
             patch.object(full_cycle._stage["stage-validate"], "run_global_checks"), \
             patch.object(
                 full_cycle._stage["stage-validate"], "run_for_package", return_value=True
             ), \
             patch.object(full_cycle._stage["stage-copr"], "check_copr_credentials"), \
             patch.object(
                 full_cycle._stage["stage-mock"],
                 "run_for_package",
                 side_effect=fake_mock_run_for_package,
             ), \
             patch.object(
                 full_cycle._stage["stage-copr"], "run_for_package", return_value=True
             ) as copr_mock:
            full_cycle.run_build_pipeline(
                packages,
                build_status,
                fedora_version="44",
                mock_chroot_name="fedora-44-x86_64",
                copr_repo=copr_repo,
                proceed=False,
            )

        return build_status, copr_mock

    def test_one_package_mock_failure_blocks_copr_for_all(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        build_status, copr_mock = self._run(
            packages, {"hyprutils": True, "Hyprland": False}
        )

        # hyprutils succeeded its own mock build, but must NOT reach Copr.
        copr_mock.assert_not_called()
        assert "blocked" in build_status["stages"]["copr"]["hyprutils"]["reason"]
        assert "blocked" in build_status["stages"]["copr"]["Hyprland"]["reason"]
        assert "Hyprland" in build_status["stages"]["copr"]["hyprutils"]["reason"]

    def test_all_mock_success_copr_runs_for_all(self):
        packages = {"hyprutils": {}, "Hyprland": {}}
        build_status, copr_mock = self._run(
            packages, {"hyprutils": True, "Hyprland": True}
        )

        assert copr_mock.call_count == 2
        called_pkgs = {c.args[0] for c in copr_mock.call_args_list}
        assert called_pkgs == {"hyprutils", "Hyprland"}

    def test_skip_copr_env_bypasses_gate_entirely(self):
        """SKIP_COPR=true still just skips -- no blocked-reason noise."""
        packages = {"hyprutils": {}, "Hyprland": {}}
        build_status = self._base_build_status()
        # Seed a prior successful copr entry, as a real repeated run would have.
        build_status["stages"]["copr"]["hyprutils"] = {"state": "success"}

        def fake_mock_run_for_package(
            pkg, meta, build_status, fedora_version, mock_chroot_name,
            proceed, mock_failed, all_pkgs,
        ):
            build_status["stages"]["mock"][pkg] = {"state": "failed"}
            mock_failed[pkg] = True
            return False

        def fake_is_cached(stage, pkg, build_status, new_hashes, forced_stages):
            return stage not in ("mock", "copr")

        with patch.object(full_cycle, "get_packages", return_value=packages), \
             patch.object(full_cycle, "compute_input_hashes", return_value={}), \
             patch.object(full_cycle, "effective_deps", return_value=set()), \
             patch.object(full_cycle, "is_cached", side_effect=fake_is_cached), \
             patch.object(full_cycle, "cache_miss_reason", return_value="test"), \
             patch.object(full_cycle, "save_build_status"), \
             patch.object(full_cycle.time, "sleep"), \
             patch.object(full_cycle._stage["stage-show-plan"], "show_plan"), \
             patch.object(full_cycle._stage["stage-validate"], "run_global_checks"), \
             patch.object(
                 full_cycle._stage["stage-validate"], "run_for_package", return_value=True
             ), \
             patch.object(full_cycle._stage["stage-copr"], "check_copr_credentials"), \
             patch.object(
                 full_cycle._stage["stage-mock"],
                 "run_for_package",
                 side_effect=fake_mock_run_for_package,
             ), \
             patch.object(
                 full_cycle._stage["stage-copr"], "run_for_package", return_value=True
             ) as copr_mock:
            full_cycle.run_build_pipeline(
                packages,
                build_status,
                fedora_version="44",
                mock_chroot_name="fedora-44-x86_64",
                copr_repo="nett00n/hyprland",
                proceed=False,
                skip_copr=True,
            )

        copr_mock.assert_not_called()
        assert build_status["stages"]["copr"]["hyprutils"]["reason"] == "SKIP_COPR"


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
        build_status = {
            "stages": {
                "srpm": {},
                "spec": {
                    pkg: {"state": "failed"}  # spec failed
                },
            },
        }
        fedora_version = "44"

        result = stage_srpm.run_for_package(
            pkg, meta, build_status, fedora_version, proceed=False
        )

        assert result is True
        assert build_status["stages"]["srpm"][pkg]["state"] == "skipped"
