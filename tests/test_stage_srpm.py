"""Tests for stage-srpm.py's source verification step (BUG-0025).

Between `spectool -g -R` and `rpmbuild -bs`, stage-srpm.py now checks every
downloaded source file against sources.lock.yaml and fails closed if a file
is unrecorded or doesn't match -- see lib.source_lock.verify.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.source_lock import save_lock, sha256_file

stage_srpm = importlib.import_module("scripts.stage-srpm")

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    yield
    build_db.close()


@pytest.fixture(autouse=True)
def lock_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SOURCES_LOCK", tmp_path / "sources.lock.yaml")


@pytest.fixture
def run_id():
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    build_db.set_stage("test-pkg", "spec", TARGET, run_id, "success")
    return run_id


def _meta():
    return {
        "version": "1.0.0",
        "release": 1,
        "url": "https://example.com/pkg",
        "source": {"archives": ["https://example.com/pkg-1.0.0.tar.gz"]},
    }


class TestSourceVerifyGate:
    def test_fails_closed_when_no_lock_entry(self, tmp_path, run_id):
        pkg = "test-pkg"
        meta = _meta()
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir),
            patch.object(stage_srpm, "ROOT", tmp_path),
            patch.object(stage_srpm, "run_cmd", return_value=(True, "", "")),
        ):
            result = stage_srpm.run_for_package(
                pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id
            )

        assert result is False
        entry = build_db.get_stage(pkg, "srpm", TARGET)
        assert entry["state"] == "failed"
        assert entry["reason"] == "source verify failed"
        log_text = (log_dir / "10-srpm.log").read_text()
        assert "no entry in sources.lock.yaml" in log_text

    def test_fails_closed_on_hash_mismatch(self, tmp_path, run_id, monkeypatch):
        pkg = "test-pkg"
        meta = _meta()
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir(parents=True)
        monkeypatch.setattr(stage_srpm, "SOURCES_DIR", sources_dir)
        (sources_dir / "pkg-1.0.0.tar.gz").write_bytes(b"tampered")
        save_lock({pkg: {"pkg-1.0.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})

        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir),
            patch.object(stage_srpm, "ROOT", tmp_path),
            patch.object(stage_srpm, "run_cmd", return_value=(True, "", "")),
        ):
            result = stage_srpm.run_for_package(
                pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id
            )

        assert result is False
        assert build_db.get_stage(pkg, "srpm", TARGET)["reason"] == "source verify failed"

    def test_passes_when_hash_matches(self, tmp_path, run_id, monkeypatch):
        pkg = "test-pkg"
        meta = _meta()
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir(parents=True)
        monkeypatch.setattr(stage_srpm, "SOURCES_DIR", sources_dir)
        tarball = sources_dir / "pkg-1.0.0.tar.gz"
        tarball.write_bytes(b"real contents")
        save_lock({pkg: {"pkg-1.0.0.tar.gz": {"sha256": sha256_file(tarball), "url": "x"}}})

        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir),
            patch.object(stage_srpm, "ROOT", tmp_path),
            patch.object(stage_srpm, "run_cmd", return_value=(True, "", "")),
            patch.object(stage_srpm, "find_srpm", return_value=str(srpm_path)),
            patch.object(stage_srpm, "copy_local_patches"),
        ):
            result = stage_srpm.run_for_package(
                pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id
            )

        assert result is True
        assert build_db.get_stage(pkg, "srpm", TARGET)["state"] == "success"

    def test_no_remote_sources_skips_check(self, tmp_path, run_id):
        """A package with no source.archives at all (e.g. tests exercising other
        fields) has nothing to verify -- must not be blocked by this gate."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)

        with (
            patch.object(stage_srpm, "get_package_log_dir", return_value=log_dir),
            patch.object(stage_srpm, "ROOT", tmp_path),
            patch.object(stage_srpm, "run_cmd", return_value=(True, "", "")),
            patch.object(stage_srpm, "find_srpm", return_value=str(srpm_path)),
            patch.object(stage_srpm, "copy_local_patches"),
        ):
            result = stage_srpm.run_for_package(
                pkg, meta, "44", proceed=False, target=TARGET, run_id=run_id
            )

        assert result is True
