"""Tests for artifact recording added to stage-srpm.py, stage-vendor.py, and
stage-mock.py in phase 3 of the yaml->sqlite migration.

Records paths/sizes of build outputs into build-report.db's `artifacts` table
so disk usage can be reported and reclaimed (see docs/todo.md).
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths

stage_srpm = importlib.import_module("scripts.stage-srpm")
stage_vendor = importlib.import_module("scripts.stage-vendor")
stage_mock = importlib.import_module("scripts.stage-mock")
stage_copr = importlib.import_module("scripts.stage-copr")

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


@pytest.fixture
def run_id():
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    # Both stage-srpm.py and stage-vendor.py skip unless spec already succeeded.
    build_db.set_stage("test-pkg", "spec", TARGET, run_id, "success")
    return run_id


class TestSrpmArtifactRecording:
    def test_success_records_srpm_artifact(self, tmp_path, monkeypatch, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"x" * 42)

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_srpm, "ROOT", tmp_path), \
             patch.object(stage_srpm, "run_cmd", return_value=(True, "", "")), \
             patch.object(stage_srpm, "find_srpm", return_value=str(srpm_path)), \
             patch.object(stage_srpm, "copy_local_patches"):
            result = stage_srpm.run_for_package(pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id)

        assert result is True
        artifacts = build_db.artifacts(package=pkg, kind="srpm")
        assert len(artifacts) == 1
        assert artifacts[0]["path"] == str(srpm_path)
        assert artifacts[0]["realm"] == "rpmbuild-volume"
        assert artifacts[0]["size_bytes"] == 42

    def test_failure_records_no_artifact(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_srpm, "ROOT", tmp_path), \
             patch.object(stage_srpm, "run_cmd", return_value=(False, "", "error")):
            result = stage_srpm.run_for_package(pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id)

        assert result is False
        assert build_db.artifacts(package=pkg, kind="srpm") == []


class TestVendorArtifactRecording:
    def test_freshly_generated_tarball_recorded(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "build_requires": ["golang"], "url": "https://example.com/pkg"}
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()

        def fake_generate(pkg_name, meta, tarball, log_path=None):
            tarball.write_bytes(b"vendor-tarball-contents")

        with patch.object(stage_vendor, "ROOT", tmp_path), \
             patch.object(stage_vendor, "SOURCES_DIR", sources_dir), \
             patch.object(stage_vendor, "generate", side_effect=fake_generate):
            result = stage_vendor.run_for_package(pkg, meta, "44", TARGET, run_id)

        assert result is True
        artifacts = build_db.artifacts(package=pkg, kind="vendor")
        assert len(artifacts) == 1
        assert artifacts[0]["realm"] == "rpmbuild-volume"
        assert artifacts[0]["size_bytes"] == len(b"vendor-tarball-contents")

    def test_cached_tarball_still_recorded(self, tmp_path, run_id):
        """Even when the tarball already exists (skip-regenerate path), it's recorded."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "build_requires": ["golang"], "url": "https://example.com/pkg"}
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()

        with patch.object(stage_vendor, "ROOT", tmp_path), \
             patch.object(stage_vendor, "SOURCES_DIR", sources_dir):
            from lib.vendor import vendor_tarball_path

            tarball = vendor_tarball_path(pkg, "1.0.0", sources_dir)
            tarball.parent.mkdir(parents=True, exist_ok=True)
            tarball.write_bytes(b"already-here")

            result = stage_vendor.run_for_package(pkg, meta, "44", TARGET, run_id)

        assert result is True
        artifacts = build_db.artifacts(package=pkg, kind="vendor")
        assert len(artifacts) == 1
        assert artifacts[0]["size_bytes"] == len(b"already-here")

    def test_not_vendored_package_records_nothing(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0"}  # no golang/cargo in build_requires

        with patch.object(stage_vendor, "ROOT", tmp_path):
            result = stage_vendor.run_for_package(pkg, meta, "44", TARGET, run_id)

        assert result is True
        assert build_db.artifacts(package=pkg) == []


class TestMissingSrpmArtifactGuard:
    """A "success" srpm row whose recorded file has vanished from disk (e.g. a
    pruned rpmbuild-volume) must not be handed to mock or submitted to Copr --
    see docs/bugs.md BUG-0015, the exact "Cannot find/open srpm" failure this
    guards against.
    """

    def test_mock_skips_when_srpm_path_missing_on_disk(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        missing_srpm = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"  # never created
        build_db.set_stage(
            pkg, "srpm", TARGET, run_id, "success", path=str(missing_srpm)
        )
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        failed: dict = {}

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir):
            result = stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed=failed,
                all_packages={pkg: meta},
                run_id=run_id,
            )

        assert result is True  # skip, not a hard failure
        assert failed[pkg] is True
        mock_entry = build_db.get_stage(pkg, "mock", TARGET)
        assert mock_entry["state"] == "skipped"
        assert mock_entry["reason"] == "srpm artifact missing"

    def test_mock_runs_when_srpm_path_present_on_disk(self, tmp_path, run_id):
        """Sanity check: an existing SRPM is not blocked by the new guard."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        failed: dict = {}

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd", return_value=(True, "", "")), \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):
            result = stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed=failed,
                all_packages={pkg: meta},
                run_id=run_id,
            )

        assert result is True
        assert failed[pkg] is False
        mock_entry = build_db.get_stage(pkg, "mock", TARGET)
        assert mock_entry["state"] == "success"

    def test_copr_skips_when_srpm_path_missing_on_disk(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        missing_srpm = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"  # never created
        build_db.set_stage(
            pkg, "srpm", TARGET, run_id, "success", path=str(missing_srpm)
        )
        build_db.set_stage(pkg, "mock", TARGET, run_id, "success")
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with patch.object(stage_copr, "get_package_log_dir", return_value=log_dir):
            result = stage_copr.run_for_package(
                pkg, meta, "44", "nett00n/hyprland", False, TARGET, run_id
            )

        assert result is True  # skip, not a hard failure
        copr_entry = build_db.get_stage(pkg, "copr", TARGET)
        assert copr_entry["state"] == "skipped"
        assert copr_entry["reason"] == "srpm artifact missing"
