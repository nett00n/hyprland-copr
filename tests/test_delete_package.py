"""#COPR-0022: tests for delete-package.py's run-scoped log discovery/cleanup.

Only the log-dir-related seams -- resolve_name()'s stray-name discovery and
main()'s cleanup -- were touched by the logs/runs/ migration; the
packages.yaml/groups.yaml/sources.lock.yaml/build-report.db removal logic is
unchanged.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, local_repo, paths

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


# --- #COPR-0013, #BUG-0071, #BUG-0070: local-repo + rpmbuild-volume cleanup ----


def _fake_source_names(monkeypatch, mapping):
    """Stub rpm_source_name: {rpm file name: source package name}."""
    monkeypatch.setattr(
        local_repo, "rpm_source_name", lambda rpm: mapping.get(rpm.name, "")
    )


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    return path


def test_remove_package_rpms_unlinks_only_matching_source_and_regenerates(
    tmp_path, monkeypatch
):
    root = tmp_path / "local-repo"
    mine_a = _touch(root / "fedora-44-x86_64" / "pkg-1.0-1.fc44.x86_64.rpm")
    mine_b = _touch(root / "fedora-43-x86_64" / "pkg-libs-1.0-1.fc43.x86_64.rpm")
    sibling = _touch(root / "fedora-44-x86_64" / "pkg-extra-2.0-1.fc44.x86_64.rpm")
    untouched = _touch(root / "fedora-42-x86_64" / "other-1.0-1.fc42.x86_64.rpm")
    srpm = _touch(root / "fedora-44-x86_64" / "pkg-1.0-1.fc44.src.rpm")
    _fake_source_names(
        monkeypatch,
        {
            mine_a.name: "pkg",
            mine_b.name: "pkg",
            sibling.name: "pkg-extra",
            untouched.name: "other",
        },
    )
    regenerated = []
    monkeypatch.setattr(
        local_repo, "regenerate_repo_metadata", lambda d: regenerated.append(d.name)
    )
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    build_db.close()

    removed = local_repo.remove_package_rpms("pkg", root=root)

    assert removed == {"fedora-44-x86_64": 1, "fedora-43-x86_64": 1}
    assert not mine_a.exists()
    assert not mine_b.exists()
    assert sibling.exists()
    assert untouched.exists()
    assert srpm.exists()  # .src.rpm is never queried or removed here
    assert sorted(regenerated) == ["fedora-43-x86_64", "fedora-44-x86_64"]
    build_db.close()


def test_remove_package_rpms_drops_ledger_rows(tmp_path, monkeypatch):
    root = tmp_path / "local-repo"
    rpm = _touch(root / "fedora-44-x86_64" / "pkg-1.0-1.fc44.x86_64.rpm")
    _fake_source_names(monkeypatch, {rpm.name: "pkg"})
    monkeypatch.setattr(local_repo, "regenerate_repo_metadata", lambda d: None)
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    build_db.close()
    build_db.record_artifact(
        str(rpm), "repo", "rpm", "pkg", "fedora-44-x86_64", "1.0-1.fc44"
    )

    local_repo.remove_package_rpms("pkg", root=root)

    assert not build_db.artifact_path_referenced("repo", str(rpm))
    build_db.close()


def test_remove_package_rpms_no_repo_dir_is_noop(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(
        local_repo, "regenerate_repo_metadata", lambda d: called.append(d)
    )

    assert local_repo.remove_package_rpms("pkg", root=tmp_path / "missing") == {}
    assert called == []


def test_remove_package_rpms_no_match_does_not_regenerate(tmp_path, monkeypatch):
    root = tmp_path / "local-repo"
    other = _touch(root / "fedora-44-x86_64" / "other-1.0-1.fc44.x86_64.rpm")
    _fake_source_names(monkeypatch, {other.name: "other"})
    called = []
    monkeypatch.setattr(
        local_repo, "regenerate_repo_metadata", lambda d: called.append(d)
    )

    assert local_repo.remove_package_rpms("pkg", root=root) == {}
    assert other.exists()
    assert called == []


def test_sweep_rpmbuild_removes_package_files_and_keeps_siblings(
    tmp_path, monkeypatch
):
    rb = tmp_path / "rpmbuild"
    gone = [
        _touch(rb / "SOURCES" / "pkg-1.0.tar.gz"),
        _touch(rb / "SOURCES" / "pkg-1.0-vendor.tar.xz"),
        _touch(rb / "SRPMS" / "pkg-1.0-1.fc44.src.rpm"),
        _touch(rb / "RPMS" / "x86_64" / "pkg-libs-1.0-1.fc44.x86_64.rpm"),
    ]
    kept = [
        _touch(rb / "SOURCES" / "pkg-extra-2.0.tar.gz"),
        _touch(rb / "SRPMS" / "pkg-extra-2.0-1.fc44.src.rpm"),
        _touch(rb / "RPMS" / "x86_64" / "pkg-extra-2.0-1.fc44.x86_64.rpm"),
    ]
    _fake_source_names(
        monkeypatch,
        {
            "pkg-libs-1.0-1.fc44.x86_64.rpm": "pkg",
            "pkg-extra-2.0-1.fc44.x86_64.rpm": "pkg-extra",
        },
    )

    count = delete_package.sweep_rpmbuild("pkg", rpmbuild=rb)

    assert count == 4
    assert not any(p.exists() for p in gone)
    assert all(p.exists() for p in kept)


def test_sweep_rpmbuild_missing_dir_is_noop(tmp_path):
    assert delete_package.sweep_rpmbuild("pkg", rpmbuild=tmp_path / "nope") == 0


def test_main_reports_rpm_and_volume_cleanup(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(delete_package, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    build_db.close()
    monkeypatch.setattr(sys, "argv", ["delete-package.py", "pkg"])
    monkeypatch.setattr(delete_package, "get_packages", lambda: {"pkg": {}})
    monkeypatch.setattr(delete_package, "write_yaml_file", lambda *a, **k: None)
    monkeypatch.setattr(delete_package, "load_groups_yaml", lambda: {})
    monkeypatch.setattr(delete_package, "load_lock", lambda: {})
    monkeypatch.setattr(
        delete_package.local_repo,
        "remove_package_rpms",
        lambda pkg: {"fedora-44-x86_64": 2, "fedora-43-x86_64": 1},
    )
    monkeypatch.setattr(delete_package, "sweep_rpmbuild", lambda pkg: 5)

    delete_package.main()

    out = capsys.readouterr().out
    assert "3 RPM(s) in local-repo" in out
    assert "5 file(s) in rpmbuild volume" in out
    build_db.close()


def test_main_already_clean_still_exits_when_nothing_matched(tmp_path, monkeypatch):
    monkeypatch.setattr(delete_package, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    build_db.close()
    monkeypatch.setattr(sys, "argv", ["delete-package.py", "ghost"])
    monkeypatch.setattr(delete_package, "get_packages", lambda: {})
    monkeypatch.setattr(delete_package, "load_groups_yaml", lambda: {})
    monkeypatch.setattr(delete_package, "load_lock", lambda: {})
    monkeypatch.setattr(delete_package, "resolve_name", lambda *a: "ghost")
    monkeypatch.setattr(delete_package.local_repo, "remove_package_rpms", lambda p: {})
    monkeypatch.setattr(delete_package, "sweep_rpmbuild", lambda p: 0)

    with pytest.raises(SystemExit) as exc:
        delete_package.main()

    assert "nothing to remove" in str(exc.value)
    build_db.close()
