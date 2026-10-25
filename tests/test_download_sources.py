"""Tests for scripts/download-sources.py (#BUG-0066: `make sources` loop moved out of the Makefile)."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

download_sources = importlib.import_module("download-sources")

PACKAGES = {"pkg-a": {}, "pkg-b": {}, "pkg-c": {}}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(download_sources, "ROOT", tmp_path)
    monkeypatch.delenv("PACKAGE", raising=False)
    monkeypatch.delenv("SKIP_PACKAGES", raising=False)
    for name in PACKAGES:
        spec_dir = tmp_path / "packages" / name
        spec_dir.mkdir(parents=True)
        (spec_dir / f"{name}.spec").write_text("Name: x\n")
    return tmp_path


def _run():
    with patch.object(download_sources, "get_packages", return_value=PACKAGES), patch.object(
        download_sources, "run_cmd", return_value=(True, "", "")
    ) as mock_run:
        return download_sources.main(), mock_run


def test_runs_spectool_for_every_package(root):
    rc, mock_run = _run()
    assert rc == 0
    specs = [c.args[0][-1] for c in mock_run.call_args_list]
    assert specs == [str(root / "packages" / n / f"{n}.spec") for n in PACKAGES]
    assert mock_run.call_args.args[0][:3] == ["spectool", "-g", "-R"]


def test_package_and_skip_select_the_set(root, monkeypatch):
    monkeypatch.setenv("PACKAGE", "pkg-a,pkg-b,pkg-c")
    monkeypatch.setenv("SKIP_PACKAGES", "pkg-b")
    rc, mock_run = _run()
    assert rc == 0
    assert [Path(c.args[0][-1]).name for c in mock_run.call_args_list] == [
        "pkg-a.spec",
        "pkg-c.spec",
    ]


def test_missing_spec_fails_before_any_download(root, capsys):
    (root / "packages" / "pkg-b" / "pkg-b.spec").unlink()
    rc, mock_run = _run()
    assert rc == 1
    mock_run.assert_not_called()
    assert "pkg-b - spec file not found" in capsys.readouterr().err


def test_spectool_failure_returns_nonzero(root):
    with patch.object(download_sources, "get_packages", return_value=PACKAGES), patch.object(
        download_sources, "run_cmd", return_value=(False, "", "boom")
    ) as mock_run:
        assert download_sources.main() == 1
    assert mock_run.call_count == 1
