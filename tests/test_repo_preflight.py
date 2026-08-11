"""Tests for scripts/lib/repo_preflight.py.

check_buildroot_repo() runs before stage-mock.py spawns mock at all, so a
missing or wrong-chroot local dependency fails in seconds with an actionable
message instead of a multi-minute dnf5 transaction-resolution failure (the
"nothing provides libdisplay-info.so.2()(64bit)" class of failure -- see
docs/CHANGELOG.md 2026-08-11).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.repo_preflight import (
    check_buildroot_repo,
    format_local_repo_remedy,
    rpm_dist_tag,
    target_dist_tag,
)

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Isolate build-report.db per test (mirrors tests/test_stage_mock.py)."""
    db_path = tmp_path / "isolated-build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


class TestTargetDistTag:
    def test_fedora_44(self):
        assert target_dist_tag("fedora-44-x86_64") == "fc44"

    def test_fedora_43(self):
        assert target_dist_tag("fedora-43-x86_64") == "fc43"

    def test_rawhide_is_unknowable(self):
        """Rawhide's dist tag floats -- a package built today may carry a
        different fcNN than one built next week -- so foreign-dist checks
        must be skipped rather than false-positive on a real rawhide repo."""
        assert target_dist_tag("fedora-rawhide-x86_64") is None


class TestRpmDistTag:
    def test_from_filename(self):
        path = Path("aquamarine-0.14.0-8.fc44.x86_64.rpm")
        assert rpm_dist_tag(path) == "fc44"

    def test_from_filename_el(self):
        path = Path("somepkg-1.0-1.el9.x86_64.rpm")
        assert rpm_dist_tag(path) == "el9"

    def test_falls_back_to_rpm_query_release(self, tmp_path):
        """A filename without a recognizable dist tag falls back to querying
        %{RELEASE} from the RPM header itself."""
        path = tmp_path / "oddly-named.rpm"
        path.write_bytes(b"not a real rpm")
        with patch("lib.repo_preflight.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "8.fc44"
            assert rpm_dist_tag(path) == "fc44"

    def test_unresolvable_returns_none(self, tmp_path):
        path = tmp_path / "oddly-named.rpm"
        path.write_bytes(b"not a real rpm")
        with patch("lib.repo_preflight.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            assert rpm_dist_tag(path) is None


class TestFormatLocalRepoRemedy:
    def test_names_package_and_gives_rebuild_command(self):
        msg = format_local_repo_remedy(["aquamarine"], "44")
        assert "aquamarine" in msg
        assert "make stage-mock PACKAGE=aquamarine FEDORA_VERSION=44" in msg
        assert "make clean-mock-cache" in msg
        assert "make clean-localrepo" in msg


class TestCheckBuildrootRepo:
    def _all_packages(self, **extra):
        packages = {
            "hyprland": {
                "version": "0.51.0",
                "release": 1,
                "depends_on": ["aquamarine"],
            },
            "aquamarine": {"version": "0.14.0", "release": 8},
        }
        packages.update(extra)
        return packages

    def test_clean_repo_no_errors(self, tmp_path):
        """A populated, matching-dist repo with the dep present -> no findings."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "aquamarine-0.14.0-8.fc44.x86_64.rpm").write_text("rpm")
        all_packages = self._all_packages()

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []

    def test_empty_repo_no_deps_needed_is_clean(self, tmp_path):
        repo_dir = tmp_path / TARGET
        all_packages = {"standalone": {"version": "1.0", "release": 1}}
        errors, warnings = check_buildroot_repo(
            "standalone",
            all_packages["standalone"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []

    def test_missing_repodata_is_warning_only(self, tmp_path):
        """A fresh target with no repodata yet is expected (first build for
        this chroot) -- stage-mock self-heals it, so this must not block."""
        repo_dir = tmp_path / TARGET
        all_packages = {"standalone": {"version": "1.0", "release": 1}}
        errors, warnings = check_buildroot_repo(
            "standalone",
            all_packages["standalone"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []
        assert any("repodata" in w for w in warnings)

    def test_foreign_dist_rpm_is_error(self, tmp_path):
        """An fc43 RPM sitting in the fedora-44 target dir should be
        structurally impossible under the per-chroot layout -- treat it as a
        hard error naming the offending file, not a silent resolution."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "aquamarine-0.14.0-10.fc43.x86_64.rpm").write_text("rpm")
        all_packages = {"standalone": {"version": "1.0", "release": 1}}

        errors, warnings = check_buildroot_repo(
            "standalone",
            all_packages["standalone"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert len(errors) == 1
        assert "aquamarine-0.14.0-10.fc43.x86_64.rpm" in errors[0]

    def test_foreign_dist_check_skipped_for_rawhide(self, tmp_path):
        rawhide_target = "fedora-rawhide-x86_64"
        repo_dir = tmp_path / rawhide_target
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "aquamarine-0.14.0-10.fc43.x86_64.rpm").write_text("rpm")
        all_packages = {"standalone": {"version": "1.0", "release": 1}}

        errors, warnings = check_buildroot_repo(
            "standalone",
            all_packages["standalone"],
            all_packages,
            rawhide_target,
            "rawhide",
            repo_dir,
        )
        assert errors == []

    def test_missing_explicit_dep_is_error(self, tmp_path):
        """depends_on is authoritative -- a missing explicit dep must block
        the build, not just warn."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        all_packages = self._all_packages()

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert len(errors) == 1
        assert "aquamarine" in errors[0]
        assert "make stage-mock PACKAGE=aquamarine FEDORA_VERSION=44" in errors[0]
        assert warnings == [] or all("aquamarine" not in w for w in warnings)

    def test_missing_inferred_dep_is_warning_not_error(self, tmp_path):
        """No explicit depends_on -- the dep is only inferred from a
        -devel build_requires, which is a heuristic and must not block."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        all_packages = {
            "hyprland": {
                "version": "0.51.0",
                "release": 1,
                "build_requires": ["aquamarine-devel"],
            },
            "aquamarine": {"version": "0.14.0", "release": 8},
        }

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []
        assert any("aquamarine" in w for w in warnings)

    def test_dep_skipped_for_this_fedora_version_is_ignored(self, tmp_path):
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        all_packages = self._all_packages(
            aquamarine={
                "version": "0.14.0",
                "release": 8,
                "fedora": {"44": {"skip": True}},
            }
        )

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []
        assert warnings == []

    def test_dep_with_skipped_mock_stage_is_ignored(self, tmp_path):
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        all_packages = self._all_packages()
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(
            "aquamarine", "mock", TARGET, run_id, "skipped", reason="config: skip"
        )

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []

    def test_case_insensitive_name_match(self, tmp_path):
        """packages.yaml keys are mixed case (e.g. "Hyprland"); the RPM on
        disk is lowercase -- the presence check must not care."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "hyprutils-0.14.0-1.fc44.x86_64.rpm").write_text("rpm")
        all_packages = {
            "Waybar": {"version": "0.11.0", "release": 1, "depends_on": ["Hyprutils"]},
            "Hyprutils": {"version": "0.14.0", "release": 1},
        }

        errors, warnings = check_buildroot_repo(
            "Waybar",
            all_packages["Waybar"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert errors == []

    def test_transitive_dep_two_hops_is_checked(self, tmp_path):
        """hyprland -> aquamarine -> hyprutils: a missing hyprutils must be
        caught even though hyprland doesn't depend on it directly."""
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "aquamarine-0.14.0-8.fc44.x86_64.rpm").write_text("rpm")
        all_packages = self._all_packages(
            aquamarine={
                "version": "0.14.0",
                "release": 8,
                "depends_on": ["hyprutils"],
            },
            hyprutils={"version": "0.14.0", "release": 1},
        )

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert len(errors) == 1
        assert "hyprutils" in errors[0]

    def test_src_rpm_does_not_count_as_present(self, tmp_path):
        repo_dir = tmp_path / TARGET
        (repo_dir / "repodata").mkdir(parents=True)
        (repo_dir / "repodata" / "repomd.xml").write_text("<repomd/>")
        (repo_dir / "aquamarine-0.14.0-8.fc44.src.rpm").write_text("srpm")
        all_packages = self._all_packages()

        errors, warnings = check_buildroot_repo(
            "hyprland",
            all_packages["hyprland"],
            all_packages,
            TARGET,
            "44",
            repo_dir,
        )
        assert len(errors) == 1
        assert "aquamarine" in errors[0]
