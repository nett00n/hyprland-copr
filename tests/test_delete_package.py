"""#COPR-0022: tests for delete-package.py's run-scoped log discovery/cleanup.

Only the log-dir-related seams -- resolve_name()'s stray-name discovery and
main()'s cleanup -- were touched by the logs/runs/ migration; the
packages.yaml/groups.yaml/sources.lock.yaml/build-report.db removal logic is
unchanged.
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths

delete_package = importlib.import_module("delete-package")


def test_resolve_name_finds_package_only_known_from_leftover_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(delete_package, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    (tmp_path / "logs" / "runs" / "3" / "fedora-44-x86_64" / "Stray-Pkg").mkdir(
        parents=True
    )

    result = delete_package.resolve_name("stray-pkg", {}, {}, {})

    assert result == "Stray-Pkg"


def test_resolve_name_none_when_nothing_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(delete_package, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    assert delete_package.resolve_name("nope", {}, {}, {}) is None


def test_main_removes_every_run_and_target_for_the_package(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(delete_package, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    build_db.close()
    run1 = tmp_path / "logs" / "runs" / "1" / "fedora-44-x86_64" / "pkg"
    run2 = tmp_path / "logs" / "runs" / "2" / "fedora-43-x86_64" / "pkg"
    other = tmp_path / "logs" / "runs" / "2" / "fedora-43-x86_64" / "other-pkg"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)
    other.mkdir(parents=True)

    monkeypatch.setattr(sys, "argv", ["delete-package.py", "pkg"])
    monkeypatch.setattr(delete_package, "get_packages", lambda: {})
    monkeypatch.setattr(delete_package, "load_groups_yaml", lambda: {})
    monkeypatch.setattr(delete_package, "load_lock", lambda: {})

    delete_package.main()

    assert not run1.exists()
    assert not run2.exists()
    assert other.exists()
    assert "2 log dir(s)" in capsys.readouterr().out
    build_db.close()
