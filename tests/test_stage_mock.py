"""Tests for scripts/stage-mock.py, focused on local-repo NVR pruning.

Nothing previously removed an old NVR from local-repo/: every mock rebuild
only ever added a file, so e.g. hyprutils-0.13.1 could sit next to 0.14.0
forever (see docs/bugs.md). prune_local_repo() keeps only the newest NVR per
(name, arch), and now also drops the matching artifact row.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths

# Load stage-mock.py module (has hyphen, can't import normally)
stage_mock = importlib.import_module("scripts.stage-mock")

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after.

    prune_local_repo() now calls build_db.delete_artifact() -- without this,
    every test in this file would touch the real repo-root build-report.db.
    """
    db_path = tmp_path / "isolated-build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _fake_rpm_query(evr_by_name_arch: dict[tuple[str, str], str]):
    """Build a fake _rpm_query that derives name/arch/version-release from an
    rpm_path's stem, keyed by (name, arch) -> "version-release".

    Test rpm filenames are expected in the form "<name>-<arch>-marker.rpm";
    the marker is only there to make filenames unique on disk.
    """

    def fake(rpm_path: Path, fmt: str) -> str:
        name, arch = rpm_path.stem.split("__")[0].split("@")
        if fmt == "%{NAME}":
            return name
        if fmt == "%{ARCH}":
            return arch
        if fmt == "%{VERSION}-%{RELEASE}":
            return evr_by_name_arch[(name, arch)]
        if "EPOCH" in fmt:
            return "0"
        raise AssertionError(f"unexpected queryformat: {fmt}")

    return fake


class TestPruneLocalRepo:
    """Test prune_local_repo() keeps only the newest NVR per (name, arch)."""

    def test_keeps_newest_removes_older(self, tmp_path, monkeypatch):
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", tmp_path)
        old = tmp_path / "hyprutils@x86_64__old.rpm"
        new = tmp_path / "hyprutils@x86_64__new.rpm"
        old.write_text("old")
        new.write_text("new")

        fake = _fake_rpm_query(
            {
                ("hyprutils", "x86_64"): "0.13.1-4",
            }
        )

        def fake_evr(rpm_path: Path) -> str:
            version_release = "0.13.1-4" if rpm_path.name == old.name else "0.14.0-1"
            return f"0:{version_release}"

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            with patch.object(stage_mock, "_evr", side_effect=fake_evr):
                removed = stage_mock.prune_local_repo()

        assert removed is True
        assert not old.exists()
        assert new.exists()

    def test_removed_file_drops_artifact_row(self, tmp_path, monkeypatch):
        """Pruning a stale RPM also removes its artifact ledger row."""
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", tmp_path)
        old = tmp_path / "hyprutils@x86_64__old.rpm"
        new = tmp_path / "hyprutils@x86_64__new.rpm"
        old.write_text("old")
        new.write_text("new")
        build_db.record_artifact(str(old), "repo", "rpm", "hyprutils", TARGET, "0.13.1-4.fc44")
        build_db.record_artifact(str(new), "repo", "rpm", "hyprutils", TARGET, "0.14.0-1.fc44")

        fake = _fake_rpm_query({("hyprutils", "x86_64"): "0.13.1-4"})

        def fake_evr(rpm_path: Path) -> str:
            version_release = "0.13.1-4" if rpm_path.name == old.name else "0.14.0-1"
            return f"0:{version_release}"

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            with patch.object(stage_mock, "_evr", side_effect=fake_evr):
                stage_mock.prune_local_repo()

        remaining_paths = {a["path"] for a in build_db.artifacts(package="hyprutils")}
        assert str(old) not in remaining_paths
        assert str(new) in remaining_paths

    def test_no_duplicates_removes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", tmp_path)
        a = tmp_path / "hyprutils@x86_64__a.rpm"
        b = tmp_path / "hyprutils-devel@x86_64__b.rpm"
        a.write_text("a")
        b.write_text("b")

        fake = _fake_rpm_query(
            {
                ("hyprutils", "x86_64"): "0.14.0-1",
                ("hyprutils-devel", "x86_64"): "0.14.0-1",
            }
        )

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            removed = stage_mock.prune_local_repo()

        assert removed is False
        assert a.exists()
        assert b.exists()

    def test_ignores_src_rpm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", tmp_path)
        src = tmp_path / "hyprutils-0.14.0-1.src.rpm"
        src.write_text("src")

        with patch.object(stage_mock, "_rpm_query") as mock_query:
            removed = stage_mock.prune_local_repo()

        mock_query.assert_not_called()
        assert removed is False
        assert src.exists()

    def test_three_versions_keeps_only_newest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", tmp_path)
        v1 = tmp_path / "hyprutils@x86_64__v1.rpm"
        v2 = tmp_path / "hyprutils@x86_64__v2.rpm"
        v3 = tmp_path / "hyprutils@x86_64__v3.rpm"
        for f in (v1, v2, v3):
            f.write_text("x")

        version_release_by_path = {
            v1: "0.11.0-1",
            v2: "0.14.0-1",
            v3: "0.13.1-4",
        }

        def fake(rpm_path: Path, fmt: str) -> str:
            if fmt == "%{NAME}":
                return "hyprutils"
            if fmt == "%{ARCH}":
                return "x86_64"
            if fmt == "%{VERSION}-%{RELEASE}":
                return version_release_by_path[rpm_path]
            return "0"

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            removed = stage_mock.prune_local_repo()

        assert removed is True
        assert not v1.exists()
        assert not v3.exists()
        assert v2.exists()  # 0.14.0-1 is newest


class TestVercmp:
    """Test _vercmp against the real rpmdev-vercmp binary (available in the
    container all tests run in)."""

    def test_older_is_less(self):
        assert stage_mock._vercmp("0:0.13.1-4", "0:0.14.0-1") == -1

    def test_newer_is_greater(self):
        assert stage_mock._vercmp("0:0.14.0-1", "0:0.13.1-4") == 1

    def test_equal(self):
        assert stage_mock._vercmp("0:0.14.0-1", "0:0.14.0-1") == 0

    def test_numeric_not_lexicographic(self):
        # Lexicographically "0.9.3" > "0.11.0", but numerically 0.11.0 is newer.
        assert stage_mock._vercmp("0:0.9.3-1", "0:0.11.0-1") == -1


class TestUpdateLocalRepo:
    """Test update_local_repo() copies mock results and prunes/regenerates."""

    def _patched_path(self, tmp_path: Path, mock_var_lib: Path):
        """Return a Path stand-in that redirects the hardcoded '/var/lib/mock'
        prefix used by update_local_repo() to a tmp dir, passing everything
        else through to the real Path."""

        def fake_path(p, *rest):
            if p == "/var/lib/mock":
                return mock_var_lib
            return Path(p, *rest)

        return fake_path

    def test_copies_and_regenerates_when_new_rpm(self, tmp_path, monkeypatch):
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-44-x86_64" / "result"
        result_dir.mkdir(parents=True)
        (result_dir / "hyprutils-0.14.0-1.fc44.x86_64.rpm").write_text("rpm")
        (result_dir / "hyprutils-0.14.0-1.fc44.src.rpm").write_text("srpm")

        local_repo = tmp_path / "local-repo"
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", local_repo)
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=False):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                copied = stage_mock.update_local_repo("fedora-44-x86_64")

        assert (local_repo / "hyprutils-0.14.0-1.fc44.x86_64.rpm").exists()
        assert not (local_repo / "hyprutils-0.14.0-1.fc44.src.rpm").exists()
        mock_regen.assert_called_once()
        # Returns the absolute path of the copied (non-src) RPM, for the
        # caller to record as an artifact.
        assert copied == [str(local_repo / "hyprutils-0.14.0-1.fc44.x86_64.rpm")]

    def test_regenerates_on_prune_alone(self, tmp_path, monkeypatch):
        """Even with no new RPMs copied, a pruning pass should still trigger
        metadata regeneration (repo content changed)."""
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-44-x86_64" / "result"
        result_dir.mkdir(parents=True)

        local_repo = tmp_path / "local-repo"
        local_repo.mkdir()
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", local_repo)
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=True):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                stage_mock.update_local_repo("fedora-44-x86_64")

        mock_regen.assert_called_once()

    def test_no_regenerate_when_nothing_changed(self, tmp_path, monkeypatch):
        """No new RPMs and no pruning: metadata is not regenerated."""
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-44-x86_64" / "result"
        result_dir.mkdir(parents=True)

        local_repo = tmp_path / "local-repo"
        local_repo.mkdir()
        monkeypatch.setattr(stage_mock, "LOCAL_REPO", local_repo)
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=False):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                stage_mock.update_local_repo("fedora-44-x86_64")

        mock_regen.assert_not_called()
