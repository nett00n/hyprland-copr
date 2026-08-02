"""Tests for scripts/refresh-checksums.py (BUG-0025)."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import paths
from lib.source_lock import load_lock, save_lock, sha256_file

refresh_checksums = importlib.import_module("scripts.refresh-checksums")


@pytest.fixture(autouse=True)
def lock_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SOURCES_LOCK", tmp_path / "sources.lock.yaml")


def _packages():
    return {
        "pkg": {
            "version": "1.0",
            "url": "https://example.com/pkg",
            "source": {"archives": ["https://example.com/pkg-1.0.tar.gz"]},
        }
    }


class TestRefresh:
    def test_downloads_and_records_new_source(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)
        content = b"tarball bytes"

        def fake_download(url, dest, timeout=60):
            dest.write_bytes(content)
            return None

        with patch.object(refresh_checksums, "_download", side_effect=fake_download):
            ok = refresh_checksums.refresh(_packages(), force=False)

        assert ok is True
        tarball = sources_dir / "pkg-1.0.tar.gz"
        assert tarball.exists()
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == sha256_file(tarball)

    def test_skips_download_when_already_present(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)
        (sources_dir / "pkg-1.0.tar.gz").write_bytes(b"already here")

        with patch.object(refresh_checksums, "_download") as mock_dl:
            ok = refresh_checksums.refresh(_packages(), force=False)

        mock_dl.assert_not_called()
        assert ok is True
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == sha256_file(
            sources_dir / "pkg-1.0.tar.gz"
        )

    def test_download_failure_reported_and_fails(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)

        with patch.object(refresh_checksums, "_download", return_value="connection refused"):
            ok = refresh_checksums.refresh(_packages(), force=False)

        assert ok is False
        assert load_lock() == {}

    def test_hash_conflict_without_force_fails(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)
        (sources_dir / "pkg-1.0.tar.gz").write_bytes(b"new bytes")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})

        with patch.object(refresh_checksums, "_download") as mock_dl:
            ok = refresh_checksums.refresh(_packages(), force=False)

        mock_dl.assert_not_called()  # file already on disk, no need to fetch
        assert ok is False
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == "deadbeef"

    def test_hash_conflict_with_force_succeeds(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)
        tarball = sources_dir / "pkg-1.0.tar.gz"
        tarball.write_bytes(b"new bytes")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})

        ok = refresh_checksums.refresh(_packages(), force=True)

        assert ok is True
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == sha256_file(tarball)


class TestCheckOnly:
    def test_reports_ok_when_clean(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)
        tarball = sources_dir / "pkg-1.0.tar.gz"
        tarball.write_bytes(b"real contents")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": sha256_file(tarball), "url": "x"}}})

        assert refresh_checksums.check_only(_packages()) is True

    def test_reports_failure_and_does_not_write(self, tmp_path, monkeypatch):
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()
        monkeypatch.setattr(refresh_checksums, "SOURCES_DIR", sources_dir)

        assert refresh_checksums.check_only(_packages()) is False
        assert load_lock() == {}
