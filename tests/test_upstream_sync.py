"""Tests for scripts/upstream-sync.py (#COPR-0004)."""

import importlib.util
from pathlib import Path

from lib import paths
from lib.upstream import worktree_path


def _load():
    spec = importlib.util.spec_from_file_location(
        "upstream_sync", Path(__file__).parent.parent / "scripts" / "upstream-sync.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSyncAll:
    def test_syncs_every_package_url(self, upstream_repo):
        mod = _load()
        errors = mod.sync_all({"widget": {"url": upstream_repo["url"]}}, jobs=1)
        assert errors == []
        assert (worktree_path(upstream_repo["url"]) / "meson.build").exists()

    def test_parallel_matches_serial(self, upstream_repo):
        mod = _load()
        packages = {"widget": {"url": upstream_repo["url"]}}
        assert mod.sync_all(packages, jobs=4) == []

    def test_reports_failures_without_aborting_siblings(self, upstream_repo, tmp_path):
        mod = _load()
        bad = (tmp_path / "gone").as_uri()
        errors = mod.sync_all(
            {"bad": {"url": bad}, "widget": {"url": upstream_repo["url"]}}, jobs=1
        )
        assert len(errors) == 1
        assert "gone" in errors[0]
        assert (worktree_path(upstream_repo["url"]) / "meson.build").exists()

    def test_no_packages_is_noop(self, upstream_repo):
        assert _load().sync_all({}, jobs=1) == []
        assert not paths.UPSTREAM_DIR.exists()
