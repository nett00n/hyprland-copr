"""Tests for lib.stage_common.record_config_skip (#BUG-0077)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.stage_common import record_config_skip

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    yield
    build_db.close()


@pytest.mark.parametrize(
    "stage", ["validate", "spec", "vendor", "srpm", "mock", "copr"]
)
def test_records_skipped_row_with_config_reason(stage):
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    record_config_skip(stage, "pkg-a", TARGET, run_id, "44")

    row = build_db.get_stage("pkg-a", stage, TARGET)
    assert row["state"] == "skipped"
    assert row["reason"] == "config: skip"


def test_prints_event_line(capsys):
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    record_config_skip("spec", "pkg-a", TARGET, run_id, "44")

    out = capsys.readouterr().out
    assert "stage=spec" in out
    assert "pkg=pkg-a" in out
    assert "state=SKIP" in out
    assert "reason=fedora:44 skip" in out
