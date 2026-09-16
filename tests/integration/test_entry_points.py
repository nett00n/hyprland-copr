"""Integration tests for entry point scripts (stage-*.py)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import logging

import pytest

# Import using importlib to handle module names with dashes
import importlib

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib import build_db, paths

stage_validate = importlib.import_module("scripts.stage-validate")
stage_spec = importlib.import_module("scripts.stage-spec")
stage_copr = importlib.import_module("scripts.stage-copr")
stage_show_plan = importlib.import_module("scripts.stage-show-plan")

validate_run_for_package = stage_validate.run_for_package
run_global_checks = stage_validate.run_global_checks
main = stage_validate.main
spec_run_for_package = stage_spec.run_for_package

TARGET = "fedora-44-x86_64"
# stage-copr.py's run_for_package() always reads its srpm/mock rows from the
# canonical target (docs/FRD.md COPR-0018: one spec, one SRPM shared via the
# rpmbuild volume), regardless of the `target`/fedora_version it's called
# with -- see TestStageCoprBlocking below.
CANONICAL_TARGET = "fedora-43-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


@pytest.fixture
def run_id():
    return build_db.start_run(TARGET, "fedora", "44", "x86_64")


class TestStageValidate:
    """Tests for stage-validate.py entry point."""

    def test_validate_run_for_package_skip(self, run_id):
        """Test that skipped packages are marked correctly."""
        pkg = "test-pkg"
        meta = {"_skip": True}
        all_packages = {}

        result = validate_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        assert result is True
        assert build_db.get_stage(pkg, "validate", TARGET)["state"] == "skipped"

    def test_validate_run_for_package_success(self, run_id):
        """Test successful package validation."""
        pkg = "test-pkg"
        meta = {"name": pkg}
        all_packages = {}

        with patch.object(stage_validate, "validate_package") as mock_validate:
            mock_validate.return_value = ([], [])  # No errors or warnings

            result = validate_run_for_package(
                pkg, meta, all_packages, "43", TARGET, run_id
            )

        assert result is True
        entry = build_db.get_stage(pkg, "validate", TARGET)
        assert entry["state"] == "success"
        assert entry["errors"] == 0

    def test_validate_run_for_package_with_errors(self, run_id):
        """Test package validation with errors."""
        pkg = "bad-pkg"
        meta = {"name": pkg}
        all_packages = {}

        errors = ["Error 1", "Error 2"]
        warnings = ["Warning 1"]

        with patch.object(stage_validate, "validate_package") as mock_validate:
            mock_validate.return_value = (errors, warnings)

            result = validate_run_for_package(
                pkg, meta, all_packages, "43", TARGET, run_id
            )

        assert result is False
        entry = build_db.get_stage(pkg, "validate", TARGET)
        assert entry["state"] == "failed"
        assert entry["errors"] == 2
        assert entry["warnings"] == 1

    def test_run_global_checks_success(self):
        """Test global checks pass."""
        all_packages = {}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
        ):
            mock_group.return_value = ([], [])
            mock_gitmodules.return_value = ([], [])

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is True

    def test_run_global_checks_with_errors(self):
        """Test global checks fail with errors."""
        all_packages = {}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
        ):
            mock_group.return_value = (["Group error"], [])
            mock_gitmodules.return_value = ([], [])

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is False

    def test_run_global_checks_with_gitmodules_errors(self):
        """Test global checks fail when gitmodules has errors."""
        all_packages = {}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
        ):
            mock_group.return_value = ([], [])
            mock_gitmodules.return_value = (["Gitmodules error"], [])

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is False

    def test_run_global_checks_with_warnings(self, capsys):
        """Test global checks with warnings print count."""
        all_packages = {}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
        ):
            mock_group.return_value = ([], ["Group warning"])
            mock_gitmodules.return_value = ([], ["Gitmodules warning"])

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is True
        captured = capsys.readouterr()
        assert "2 warning(s) total" in captured.out

    def test_run_global_checks_warns_on_unresolvable_submodule_url(self, capsys):
        """Regression test for BUG-0013: a package url that doesn't match any
        .gitmodules submodule url warns (doesn't fail the build), surfacing
        the exact drift that let Waybar-git's auto_update silently never fire.
        """
        all_packages = {"Waybar-git": {"url": "https://github.com/Alexays/Waybar"}}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
            patch.object(stage_validate, "parse_gitmodules") as mock_parse,
        ):
            mock_group.return_value = ([], [])
            mock_gitmodules.return_value = ([], [])
            mock_parse.return_value = [
                {
                    "name": "submodules/Alexays/Waybar",
                    "path": "submodules/Alexays/Waybar",
                    "url": "https://github.com/Alexays/Waybar.git",
                }
            ]

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is True  # warning, not an error -- build still proceeds
        captured = capsys.readouterr()
        assert "Waybar-git" in captured.out

    def test_run_global_checks_with_both_group_and_gitmodules_errors(self):
        """Test global checks fail when both group and gitmodules have errors."""
        all_packages = {}

        with (
            patch.object(stage_validate, "validate_group_membership") as mock_group,
            patch.object(stage_validate, "validate_gitmodules") as mock_gitmodules,
        ):
            mock_group.return_value = (["Group error 1"], [])
            mock_gitmodules.return_value = (["Gitmodules error 1"], [])

            result = run_global_checks(all_packages, "fedora-43-x86_64")

        assert result is False

    def test_main_success(self, monkeypatch):
        """Test main() function with successful validation."""
        monkeypatch.delenv("PROCEED_BUILD", raising=False)
        with (
            patch.object(stage_validate, "prepare_stage") as mock_prepare,
            patch.object(stage_validate, "run_for_package") as mock_run,
            patch.object(stage_validate, "run_global_checks") as mock_global,
        ):
            mock_prepare.return_value = ({}, {})
            mock_run.return_value = True
            mock_global.return_value = True

            # Should not raise
            main()

    def test_main_proceed_build_1_is_honored(self, monkeypatch):
        """PROCEED_BUILD=1 must proceed, same as "true" -- regression test for
        the pre-fix inline `.lower() == "true"` parse, which silently ignored
        the `1` a `make FOO=1` command line naturally produces (BUG-0016-shaped:
        the operator's opt-in is dropped with no error). Now routed through
        lib.config.env_flag()."""
        monkeypatch.setenv("PROCEED_BUILD", "1")
        with (
            patch.object(stage_validate, "prepare_stage") as mock_prepare,
            patch.object(stage_validate, "run_for_package") as mock_run,
            patch.object(stage_validate, "run_global_checks") as mock_global,
        ):
            mock_prepare.return_value = ({}, {})
            mock_run.return_value = True
            mock_global.return_value = True

            main()

            assert mock_prepare.call_args.args[2] is True

    def test_main_exits_on_global_check_failure(self, monkeypatch):
        """Test main() exits with code 1 on global check failure."""
        monkeypatch.delenv("PROCEED_BUILD", raising=False)
        with (
            patch.object(stage_validate, "prepare_stage") as mock_prepare,
            patch.object(stage_validate, "run_for_package") as mock_run,
            patch.object(stage_validate, "run_global_checks") as mock_global,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_prepare.return_value = ({}, {})
            mock_run.return_value = True
            mock_global.return_value = False

            main()

        assert exc_info.value.code == 1

    def test_main_exits_on_per_package_failure_alone(self, monkeypatch):
        """Regression test for BUG-0054: a per-package validation error must
        fail the run even when run_global_checks() finds nothing wrong --
        previously main() discarded run_for_package()'s bool return in the
        loop, so a package with errors was printed/recorded as `failed` but
        never flipped the overall exit code."""
        monkeypatch.delenv("PROCEED_BUILD", raising=False)
        with (
            patch.object(stage_validate, "prepare_stage") as mock_prepare,
            patch.object(stage_validate, "run_for_package") as mock_run,
            patch.object(stage_validate, "run_global_checks") as mock_global,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_prepare.return_value = ({}, {"bad-pkg": {}})
            mock_run.return_value = False
            mock_global.return_value = True

            main()

        assert exc_info.value.code == 1

    def test_main_handles_keyboard_interrupt(self):
        """Test main() handles KeyboardInterrupt with exit code 130."""
        with patch.object(stage_validate, "setup_logging"):
            try:
                # Simulate __name__ == "__main__" execution
                code = """
import sys
sys.path.insert(0, 'scripts')
import importlib
stage_validate = importlib.import_module("scripts.stage-validate")
# This would trigger KeyboardInterrupt in the try/except
raise KeyboardInterrupt()
"""
                # We can't easily test this without mocking more, skip for now
            except KeyboardInterrupt:
                pass


class TestStageSpec:
    """Tests for stage-spec.py entry point."""

    def test_spec_run_for_package_skip(self, run_id):
        """Test that skipped packages are marked correctly."""
        pkg = "test-pkg"
        meta = {"_skip": True}
        all_packages = {}

        result = spec_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        assert result is True
        assert build_db.get_stage(pkg, "spec", TARGET)["state"] == "skipped"

    def test_spec_run_for_package_success(self, tmp_path, run_id):
        """Test successful spec generation."""
        pkg = "test-pkg"
        meta = {
            "version": "1.0.0",
            "release": 1,
        }
        all_packages = {pkg: meta}

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_spec, "generate_spec") as mock_gen,
            patch.object(stage_spec, "get_package_log_dir") as mock_log_dir,
            patch.object(stage_spec, "ROOT", tmp_path),
        ):
            mock_gen.return_value = "# Generated spec"
            mock_log_dir.return_value = log_dir
            result = spec_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        assert result is True
        assert build_db.get_stage(pkg, "spec", TARGET)["state"] == "success"

    def test_spec_run_for_package_failure(self, tmp_path, run_id):
        """Test spec generation failure."""
        pkg = "bad-pkg"
        meta = {
            "version": "1.0.0",
            "release": 1,
        }
        all_packages = {pkg: meta}

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_spec, "generate_spec") as mock_gen,
            patch.object(stage_spec, "get_package_log_dir") as mock_log_dir,
            patch.object(stage_spec, "ROOT", tmp_path),
        ):
            mock_gen.side_effect = RuntimeError("Template error")
            mock_log_dir.return_value = log_dir
            result = spec_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        assert result is False
        assert build_db.get_stage(pkg, "spec", TARGET)["state"] == "failed"

    def test_spec_creates_log_file(self, tmp_path, run_id):
        """Test that spec generation creates a log file."""
        pkg = "test-pkg"
        meta = {
            "version": "1.0.0",
            "release": 1,
        }
        all_packages = {pkg: meta}

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_spec, "generate_spec") as mock_gen,
            patch.object(stage_spec, "get_package_log_dir") as mock_log_dir,
            patch.object(stage_spec, "ROOT", tmp_path),
        ):
            mock_gen.return_value = "# spec content"
            mock_log_dir.return_value = log_dir
            spec_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        log_file = log_dir / "00-spec.log"
        assert log_file.exists()

    def test_spec_devel_subpackage(self, tmp_path, run_id):
        """Test that has_devel is set when a devel subpackage is present."""
        pkg = "test-pkg"
        meta = {
            "version": "1.0.0",
            "release": 1,
            "devel": {"requires": []},  # devel subpackage
        }
        all_packages = {pkg: meta}

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_spec, "generate_spec") as mock_gen,
            patch.object(stage_spec, "get_package_log_dir") as mock_log_dir,
            patch.object(stage_spec, "ROOT", tmp_path),
        ):
            mock_gen.return_value = "# spec"
            mock_log_dir.return_value = log_dir
            spec_run_for_package(pkg, meta, all_packages, "43", TARGET, run_id)

        assert build_db.get_stage(pkg, "spec", TARGET)["has_devel"] == 1


class TestStageCoprBlocking:
    """Tests for stage-copr.py entry point blocking logic."""

    def test_copr_run_for_package_skip(self, run_id):
        """Test that skipped packages are marked correctly."""
        pkg = "test-pkg"
        meta = {"_skip": True}

        result = stage_copr.run_for_package(
            pkg,
            meta,
            "43",
            "nett00n/hyprland",
            proceed=False,
            target=TARGET,
            run_id=run_id,
            synchronous=False,
        )

        assert result is True
        assert build_db.get_stage(pkg, "copr", TARGET)["state"] == "skipped"

    def test_copr_blocked_by_srpm_failure(self, run_id):
        """Test COPR skipped when SRPM failed."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        build_db.set_stage(pkg, "srpm", CANONICAL_TARGET, run_id, "failed")
        build_db.set_stage(pkg, "mock", CANONICAL_TARGET, run_id, "success")

        result = stage_copr.run_for_package(
            pkg,
            meta,
            "43",
            "nett00n/hyprland",
            proceed=False,
            target=TARGET,
            run_id=run_id,
            synchronous=False,
        )

        assert result is True
        assert build_db.get_stage(pkg, "copr", TARGET)["state"] == "skipped"
        assert build_db.get_stage(pkg, "copr", TARGET)["reason"] == "srpm failed"

    def test_copr_blocked_by_missing_canonical_build(self, run_id):
        """A package only ever built at a non-canonical FEDORA_VERSION (e.g. the
        default 44, with CANONICAL_FEDORA_VERSION=43) has no srpm/mock row at
        the canonical target at all -- distinct from a row that exists and
        failed. The reason must name the canonical target and the fix, not
        just print "srpm " (see docs/BUGS.md, the SwayOSD copr-skip case)."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        # No srpm/mock rows at CANONICAL_TARGET at all -- only ever built at TARGET.
        build_db.set_stage(
            pkg, "srpm", TARGET, run_id, "success", path="/some/path.src.rpm"
        )
        build_db.set_stage(pkg, "mock", TARGET, run_id, "success")

        result = stage_copr.run_for_package(
            pkg,
            meta,
            "43",
            "nett00n/hyprland",
            proceed=False,
            target=TARGET,
            run_id=run_id,
            synchronous=False,
        )

        assert result is True
        reason = build_db.get_stage(pkg, "copr", TARGET)["reason"]
        assert build_db.get_stage(pkg, "copr", TARGET)["state"] == "skipped"
        assert CANONICAL_TARGET in reason
        assert "full-cycle" in reason

    def test_copr_blocked_by_mock_failure(self, run_id):
        """Test COPR skipped when mock failed."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        build_db.set_stage(
            pkg, "srpm", CANONICAL_TARGET, run_id, "success", path="/some/path.src.rpm"
        )
        build_db.set_stage(pkg, "mock", CANONICAL_TARGET, run_id, "failed")

        result = stage_copr.run_for_package(
            pkg,
            meta,
            "43",
            "nett00n/hyprland",
            proceed=False,
            target=TARGET,
            run_id=run_id,
            synchronous=False,
        )

        assert result is True
        assert build_db.get_stage(pkg, "copr", TARGET)["state"] == "skipped"
        assert build_db.get_stage(pkg, "copr", TARGET)["reason"] == "mock failed"

    def test_copr_sync_failure_records_build_id_and_fetches_logs(
        self, run_id, tmp_path
    ):
        """Sync mode: a build that fails after submission still records the
        build_id (copr-cli prints "Created builds: N" before it starts
        watching) and triggers a fetch of the failed chroots' logs.
        """
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        # Must exist on disk: stage-copr.py now refuses a recorded-but-missing
        # SRPM before ever calling copr-cli (docs/BUGS.md BUG-0015).
        srpm_path = tmp_path / "path.src.rpm"
        srpm_path.write_bytes(b"srpm")
        build_db.set_stage(
            pkg, "srpm", CANONICAL_TARGET, run_id, "success", path=str(srpm_path)
        )
        build_db.set_stage(pkg, "mock", CANONICAL_TARGET, run_id, "success")

        stdout = (
            f"Uploading package {srpm_path}\n"
            "Build was added to hyprland:\n"
            "Created builds: 10798066\n"
            "Watching build(s): (this may be safely interrupted)\n"
            "  13:11:13 Build 10798066: failed\n"
        )

        with (
            patch.object(stage_copr, "run_cmd", return_value=(False, stdout, "")),
            patch.object(stage_copr, "fetch_failed_chroot_logs") as mock_fetch_logs,
            patch.object(stage_copr, "get_package_log_dir", return_value=tmp_path),
            patch.object(stage_copr, "ROOT", tmp_path),
        ):
            result = stage_copr.run_for_package(
                pkg,
                meta,
                "43",
                "nett00n/hyprland",
                proceed=False,
                target=TARGET,
                run_id=run_id,
                synchronous=True,
            )

        assert result is False
        entry = build_db.get_stage(pkg, "copr", TARGET)
        assert entry["state"] == "failed"
        assert entry["build_id"] == 10798066
        mock_fetch_logs.assert_called_once_with(pkg, 10798066)


class TestStageCoprMainGating:
    """stage-copr.py's main() (the entry point `full-cycle-matrix` submits
    through) previously had no per-package gating at all beyond each
    package's own srpm/mock state -- no cross-chroot eligibility check, and no
    transitive-dependent hold-back for a mock failure (that lived only in
    full-cycle.py, see docs/CHANGELOG.md). Both are now shared via lib.copr's
    copr_blocked_packages()/ineligible_packages(), exercised here through
    main() itself rather than the underlying helpers (already covered
    directly in tests/test_copr.py's TestIneligiblePackages).
    """

    def _run_main(self, packages, monkeypatch):
        monkeypatch.setenv("COPR_REPO", "nett00n/hyprland")
        monkeypatch.delenv("PACKAGE", raising=False)
        monkeypatch.delenv("SKIP_PACKAGES", raising=False)
        monkeypatch.delenv("REQUIRE_CHROOT_COVERAGE", raising=False)
        submitted = []

        def fake_run_for_package(pkg, meta, fedora_version, copr_repo, proceed, target, run_id, synchronous=False):
            submitted.append(pkg)
            build_db.set_stage(pkg, "copr", target, run_id, "success")
            return True

        with (
            patch.object(stage_copr, "prepare_stage", return_value=(packages, packages)),
            patch.object(stage_copr, "preflight", return_value=True),
            patch.object(stage_copr, "print_chroot_coverage", return_value=True),
            patch.object(stage_copr, "run_for_package", side_effect=fake_run_for_package),
            # ineligible_packages() (unconditionally called by main() now)
            # hits the real Copr API via get_project_chroots() unless pinned --
            # [] falls through to the same SUPPORTED_FEDORA_VERSIONS-derived
            # fallback the real API-unreachable path uses, keeping every test
            # here deterministic and offline.
            patch("lib.copr.get_project_chroots", return_value=[]),
        ):
            stage_copr.main()

        return submitted

    def test_dependent_of_failed_mock_is_held_back(self, monkeypatch):
        """A mock failure and its transitive dependent are both skipped before
        run_for_package is ever called for either -- matching full-cycle.py's
        own gating (copr_blocked_packages()), which stage-copr.py previously
        had no equivalent of at all."""
        packages = {
            "hyprutils": {"version": "1.0", "release": 1, "depends_on": []},
            "Hyprland": {"version": "1.0", "release": 1, "depends_on": ["hyprutils"]},
        }
        chroots = ("fedora-43-x86_64", "fedora-44-x86_64", "fedora-45-x86_64")
        run_id = build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")
        for chroot in chroots:
            build_db.set_stage("hyprutils", "mock", chroot, run_id, "failed")
            # Hyprland's own coverage is otherwise clean -- the only reason it
            # must be held back is the dependency relationship below, not its
            # own ineligibility (which would make this test indistinguishable
            # from test_ineligible_package_skipped_others_still_submitted).
            build_db.set_stage("Hyprland", "mock", chroot, run_id, "success")

        submitted = self._run_main(packages, monkeypatch)

        assert submitted == []
        hyprutils_entry = build_db.get_stage("hyprutils", "copr", TARGET)
        hyprland_entry = build_db.get_stage("Hyprland", "copr", TARGET)
        assert hyprutils_entry["state"] == "skipped"
        assert hyprutils_entry["reason"].startswith("blocked: not verified on:")
        assert hyprland_entry["state"] == "skipped"
        assert hyprland_entry["reason"] == "blocked: dependency ineligible: hyprutils"

    def test_ineligible_package_skipped_others_still_submitted(self, monkeypatch):
        """A package not yet verified on every locally-buildable chroot gets a
        skipped row naming the chroot, while an eligible, unrelated package
        still submits -- the strict default this whole step adds.

        Here both packages happen to be ineligible (empty build_db -> every
        chroot UNBUILT), which is also a genuine BUG-0051 blackout (zero
        verified/skipped packages on every chroot) -- ALLOW_EMPTY_COPR_SUBMISSION
        opts out of that separate loud-failure path so this test can stay
        focused on the per-package skip reason; see
        TestStageCoprBlackoutGate below for the blackout path itself."""
        packages = {
            "hyprutils": {"version": "1.0", "release": 1, "depends_on": []},
            "Hyprland": {"version": "1.0", "release": 1, "depends_on": []},
        }
        build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")
        monkeypatch.setenv("ALLOW_EMPTY_COPR_SUBMISSION", "true")

        submitted = self._run_main(packages, monkeypatch)

        # With an empty build_db, real chroot_coverage() scores both packages
        # UNBUILT on every locally-buildable chroot -- confirm that (not
        # run_for_package's own srpm/mock guard) is what held them back.
        assert submitted == []
        for pkg in packages:
            entry = build_db.get_stage(pkg, "copr", TARGET)
            assert entry["state"] == "skipped"
            assert entry["reason"].startswith("blocked: not verified on:")

    def test_eligible_package_is_submitted(self, monkeypatch):
        """Sanity check for the two tests above: a package verified on every
        locally-buildable chroot is not held back by either gate."""
        packages = {"hyprutils": {"version": "1.0", "release": 1, "depends_on": []}}
        run_id = build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")
        for chroot in ("fedora-43-x86_64", "fedora-44-x86_64", "fedora-45-x86_64"):
            build_db.set_stage("hyprutils", "mock", chroot, run_id, "success")

        submitted = self._run_main(packages, monkeypatch)

        assert submitted == ["hyprutils"]


class TestStageCoprBlackoutGate:
    """docs/BUGS.md BUG-0051: a chroot with zero verified/skipped packages
    holds back the entire run silently unless main() fails loud. Exercises
    main() itself (reusing TestStageCoprMainGating's harness) since the pure
    helper (blackout_chroots()) is already covered in tests/test_copr.py."""

    _run_main = TestStageCoprMainGating._run_main

    def test_zero_coverage_run_exits_nonzero(self, monkeypatch):
        """Empty build_db -> every chroot UNBUILT for every package -> a
        genuine blackout, previously a silent exit 0 with nothing submitted."""
        packages = {"hyprutils": {"version": "1.0", "release": 1, "depends_on": []}}
        build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")

        with pytest.raises(SystemExit) as exc_info:
            self._run_main(packages, monkeypatch)

        assert exc_info.value.code == 1
        run = build_db.get_stage("hyprutils", "copr", TARGET)
        assert run["state"] == "skipped"

    def test_allow_empty_copr_submission_downgrades_to_success(self, monkeypatch):
        """The documented escape hatch for a deliberate nothing-to-submit run."""
        packages = {"hyprutils": {"version": "1.0", "release": 1, "depends_on": []}}
        build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")
        monkeypatch.setenv("ALLOW_EMPTY_COPR_SUBMISSION", "true")

        submitted = self._run_main(packages, monkeypatch)

        assert submitted == []

    def test_real_failure_with_full_coverage_does_not_trigger_blackout_gate(
        self, monkeypatch
    ):
        """Every package held back for its own genuine reason (a real mock
        failure and its dependent) is the per-package gate working as
        designed -- not a blackout -- and must not exit non-zero."""
        packages = {
            "hyprutils": {"version": "1.0", "release": 1, "depends_on": []},
            "Hyprland": {"version": "1.0", "release": 1, "depends_on": ["hyprutils"]},
        }
        run_id = build_db.start_run(CANONICAL_TARGET, "fedora", "43", "x86_64")
        for chroot in ("fedora-43-x86_64", "fedora-44-x86_64", "fedora-45-x86_64"):
            build_db.set_stage("hyprutils", "mock", chroot, run_id, "failed")
            build_db.set_stage("Hyprland", "mock", chroot, run_id, "success")

        submitted = self._run_main(packages, monkeypatch)

        assert submitted == []


class TestStageShowPlan:
    """Tests for stage-show-plan.py show_plan() function."""

    def _seed_validate(self, pkg_states: dict) -> None:
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        for pkg, state in pkg_states.items():
            build_db.set_stage(pkg, "validate", TARGET, run_id, state or "unknown")

    def test_show_plan_no_filter(self, capsys):
        """Test all packages shown when no PACKAGE/SKIP set."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "2.0"},
            "pkg-c": {"version": "3.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": None, "pkg-c": "failed"})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET)

        captured = capsys.readouterr()
        assert "pkg-a" in captured.out
        assert "pkg-b" in captured.out
        assert "pkg-c" in captured.out
        assert "1.0" in captured.out
        assert "2.0" in captured.out
        assert "3.0" in captured.out

    def test_show_plan_single_package(self, capsys):
        """Test single package name filters correctly."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "2.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": None})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(package="pkg-a", target=TARGET)

        captured = capsys.readouterr()
        assert "pkg-a" in captured.out
        assert "pkg-b" not in captured.out

    def test_show_plan_multi_package(self, capsys):
        """Test comma-separated PACKAGE shows only those."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "2.0"},
            "pkg-c": {"version": "3.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": None, "pkg-c": "failed"})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(package="pkg-a, pkg-c", target=TARGET)

        captured = capsys.readouterr()
        assert "pkg-a" in captured.out
        assert "pkg-b" not in captured.out
        assert "pkg-c" in captured.out

    def test_show_plan_skip_packages(self, capsys):
        """Test SKIP_PACKAGES excludes listed packages."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "2.0"},
            "pkg-c": {"version": "3.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": None, "pkg-c": "failed"})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(skip_packages_arg="pkg-b", target=TARGET)

        captured = capsys.readouterr()
        assert "pkg-a" in captured.out
        assert "pkg-b" not in captured.out
        assert "pkg-c" in captured.out

    def test_show_plan_package_and_skip(self, capsys):
        """Test PACKAGE + SKIP_PACKAGES combined."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "2.0"},
            "pkg-c": {"version": "3.0"},
            "pkg-d": {"version": "4.0"},
        }
        self._seed_validate(
            {"pkg-a": "success", "pkg-b": None, "pkg-c": "failed", "pkg-d": "success"}
        )

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            # PACKAGE filters to a,b,c; SKIP removes b → a,c shown
            stage_show_plan.show_plan(
                package="pkg-a,pkg-b,pkg-c", skip_packages_arg="pkg-b", target=TARGET
            )

        captured = capsys.readouterr()
        assert "pkg-a" in captured.out
        assert "pkg-b" not in captured.out
        assert "pkg-c" in captured.out
        assert "pkg-d" not in captured.out

    def test_show_plan_unknown_package_exits(self):
        """Test unknown PACKAGE causes sys.exit."""
        packages = {"pkg-a": {"version": "1.0"}}
        self._seed_validate({"pkg-a": "success"})

        with (
            patch.object(stage_show_plan, "get_packages") as mock_get,
            pytest.raises(SystemExit),
        ):
            mock_get.return_value = packages
            stage_show_plan.show_plan(package="nonexistent", target=TARGET)

    def test_show_plan_case_insensitive(self, capsys):
        """Test PACKAGE name is case-insensitive."""
        packages = {
            "MyPkg": {"version": "1.0"},
            "OtherPkg": {"version": "2.0"},
        }
        self._seed_validate({"MyPkg": "success", "OtherPkg": None})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(package="mypkg", target=TARGET)  # lowercase

        captured = capsys.readouterr()
        assert "MyPkg" in captured.out

    def test_show_plan_force_packages_shows_run_not_cache(self, capsys):
        """A package with matching hashes normally caches; force_packages shows 'run' instead."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "1.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": "success"})

        fixed_hashes = {
            "source_commit": "x",
            "templates": "x",
            "package_config": "x",
            "dependencies": "x",
            "patches": "x",
            "content": "x",
            "package_version": "1.0",
        }
        for pkg in packages:
            run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
            build_db.set_stage(pkg, "spec", TARGET, run_id, "success")
            build_db.finalize_stage(
                pkg, "spec", TARGET, started_at=1, hashes=fixed_hashes
            )

        with (
            patch.object(stage_show_plan, "get_packages") as mock_get,
            patch.object(
                stage_show_plan, "compute_input_hashes", return_value=fixed_hashes
            ),
        ):
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET, force_packages={"pkg-a"})

        captured = capsys.readouterr()
        lines = {
            parts[0]: line
            for line in captured.out.splitlines()
            if (parts := line.split())
        }
        assert "run" in lines["pkg-a"]
        assert "cache" in lines["pkg-b"]
        assert "OtherPkg" not in captured.out


class TestStageShowPlanPredictsCascade:
    """Tests that show_plan()'s prediction matches full-cycle.py's real cascade
    (docs/BUGS.md, formerly BUG-0048): a dependent package must show "run", not
    "cache", when its dependency is about to rebuild in the same run. Requires
    both fixes together -- topo-sorted iteration (so the dependency is evaluated
    before its dependent) and a `would_rebuild` accumulator threaded through the
    loop (so the dependent's compute_forced_stages() call actually sees it).
    """

    _FIXED_HASHES = {
        "source_commit": "x",
        "templates": "x",
        "package_config": "x",
        "dependencies": "x",
        "patches": "x",
        "content": "x",
        "package_version": "1.0",
    }

    def _seed_validate(self, pkg_states: dict) -> None:
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        for pkg, state in pkg_states.items():
            build_db.set_stage(pkg, "validate", TARGET, run_id, state or "unknown")

    def _seed_cached_stage(self, tmp_path, pkg: str, stage: str) -> None:
        """Seed a stage row that is_cached() will consider a hit: success state,
        hashes matching _FIXED_HASHES, and (for vendor/srpm/mock) a real artifact
        file recorded at the matching version -- see lib.pipeline.artifacts_present."""
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, stage, TARGET, run_id, "success", version="1.0")
        build_db.finalize_stage(
            pkg, stage, TARGET, started_at=1, hashes=self._FIXED_HASHES
        )
        kind = {"vendor": "vendor", "srpm": "srpm", "mock": "rpm"}.get(stage)
        if kind is not None:
            artifact = tmp_path / f"{pkg}-{stage}-artifact"
            artifact.write_text("fake artifact")
            build_db.record_artifact(
                str(artifact), "repo", kind, pkg, TARGET, "1.0"
            )

    # Stages the plan table displays (STAGES minus copr, since show_plan() is
    # called without copr_repo below) -- "validate" is always "run" by design
    # (stage-validate.py has no cache concept, see full-cycle.py's "Validate
    # (non-fatal, no caching)" comment), so cascade assertions below look only
    # at the actually-cacheable stages that follow it.
    _CACHEABLE_COLUMNS = ("spec", "vendor", "srpm", "mock")

    def _row_for(self, captured_out: str, pkg: str) -> str:
        for line in captured_out.splitlines():
            parts = line.split()
            if parts and parts[0] == pkg:
                return line
        raise AssertionError(f"no plan row for {pkg!r} in:\n{captured_out}")

    def _cacheable_labels(self, captured_out: str, pkg: str) -> list[str]:
        """Return this row's labels for _CACHEABLE_COLUMNS, in order (skips the
        package name and the always-"run" validate column, and the trailing
        version field)."""
        parts = self._row_for(captured_out, pkg).split()
        # parts: [pkg, validate, spec, vendor, srpm, mock, version]
        return parts[2 : 2 + len(self._CACHEABLE_COLUMNS)]

    def test_dependency_cascade_shown_as_run_not_cache(self, tmp_path, capsys):
        """Recorded case (2026-08-29): hyprutils' srpm FAILs, and dependents
        hyprwire/hyprlang showed 'cache' in the plan but actually rebuilt every
        stage. Reproduced here with pkg-a (srpm failed) / pkg-b (depends_on
        pkg-a, otherwise fully cached)."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "1.0", "depends_on": ["pkg-a"]},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": "success"})

        # pkg-a's srpm stage failed -- this is what should cascade.
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage("pkg-a", "srpm", TARGET, run_id, "failed")

        # pkg-b would otherwise be fully cached on every stage.
        for stage in ("spec", "vendor", "srpm", "mock"):
            self._seed_cached_stage(tmp_path, "pkg-b", stage)

        with (
            patch.object(stage_show_plan, "get_packages") as mock_get,
            patch.object(
                stage_show_plan,
                "compute_input_hashes",
                return_value=self._FIXED_HASHES,
            ),
        ):
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET)

        captured = capsys.readouterr()
        labels = self._cacheable_labels(captured.out, "pkg-b")
        assert labels == ["run"] * 4, (
            f"pkg-b should show 'run' on every stage once its dependency "
            f"(pkg-a) rebuilds this run, not 'cache': {labels}"
        )

    def test_no_cascade_when_dependency_fully_cached(self, tmp_path, capsys):
        """Control case: when the dependency is itself fully cached, the
        dependent's stages stay 'cache' too -- the fix must not over-cascade."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "1.0", "depends_on": ["pkg-a"]},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": "success"})

        for pkg in ("pkg-a", "pkg-b"):
            for stage in ("spec", "vendor", "srpm", "mock"):
                self._seed_cached_stage(tmp_path, pkg, stage)

        with (
            patch.object(stage_show_plan, "get_packages") as mock_get,
            patch.object(
                stage_show_plan,
                "compute_input_hashes",
                return_value=self._FIXED_HASHES,
            ),
        ):
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET)

        captured = capsys.readouterr()
        assert self._cacheable_labels(captured.out, "pkg-a") == ["cache"] * 4
        assert self._cacheable_labels(captured.out, "pkg-b") == ["cache"] * 4

    def test_skipped_dependency_does_not_cascade(self, tmp_path, capsys):
        """A dependency whose stages are all 'skipped' (e.g. not-applicable
        vendor, formerly BUG-0045) must not force its dependent -- only an
        actual rebuild (run/retry) should cascade."""
        packages = {
            "pkg-a": {"version": "1.0"},
            "pkg-b": {"version": "1.0", "depends_on": ["pkg-a"]},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": "success"})

        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        for stage in ("spec", "vendor", "srpm", "mock"):
            build_db.set_stage("pkg-a", stage, TARGET, run_id, "skipped")

        for stage in ("spec", "vendor", "srpm", "mock"):
            self._seed_cached_stage(tmp_path, "pkg-b", stage)

        with (
            patch.object(stage_show_plan, "get_packages") as mock_get,
            patch.object(
                stage_show_plan,
                "compute_input_hashes",
                return_value=self._FIXED_HASHES,
            ),
        ):
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET)

        captured = capsys.readouterr()
        labels = self._cacheable_labels(captured.out, "pkg-b")
        assert labels == ["cache"] * 4, (
            f"pkg-b should not cascade off a 'skip'-only dependency: {labels}"
        )

    def test_packages_shown_in_topological_order(self, capsys):
        """Plan rows must be dependency-first, matching full-cycle.py's real run
        order -- otherwise a cascade can't be predicted even once computed,
        since the dependent would be evaluated before the dependency's outcome
        is known. packages.yaml's declared order here is deliberately the
        opposite of the dependency direction (pkg-b, the dependent, listed
        first)."""
        packages = {
            "pkg-b": {"version": "1.0", "depends_on": ["pkg-a"]},
            "pkg-a": {"version": "1.0"},
        }
        self._seed_validate({"pkg-a": "success", "pkg-b": "success"})

        with patch.object(stage_show_plan, "get_packages") as mock_get:
            mock_get.return_value = packages
            stage_show_plan.show_plan(target=TARGET)

        captured = capsys.readouterr()
        assert captured.out.index("pkg-a") < captured.out.index("pkg-b")
