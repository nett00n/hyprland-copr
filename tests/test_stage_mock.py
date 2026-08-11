"""Tests for scripts/stage-mock.py, focused on local-repo NVR pruning.

Nothing previously removed an old NVR from local-repo/<target>/: every mock
rebuild only ever added a file, so e.g. hyprutils-0.13.1 could sit next to
0.14.0 forever (see docs/bugs.md). prune_local_repo() keeps only the newest
NVR per (name, arch) *within one target's directory*, and now also drops the
matching artifact row. local-repo is scoped per chroot (docs/CHANGELOG.md
2026-08-11) specifically so an fc43 and an fc44 build of the same package
never compete against each other in the first place -- see
TestPruneLocalRepo::test_different_targets_never_compete below.
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
    """Test prune_local_repo(repo_dir) keeps only the newest NVR per (name, arch)."""

    def test_keeps_newest_removes_older(self, tmp_path):
        repo_dir = tmp_path / TARGET
        repo_dir.mkdir()
        old = repo_dir / "hyprutils@x86_64__old.rpm"
        new = repo_dir / "hyprutils@x86_64__new.rpm"
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
                removed = stage_mock.prune_local_repo(repo_dir)

        assert removed is True
        assert not old.exists()
        assert new.exists()

    def test_removed_file_drops_artifact_row(self, tmp_path):
        """Pruning a stale RPM also removes its artifact ledger row."""
        repo_dir = tmp_path / TARGET
        repo_dir.mkdir()
        old = repo_dir / "hyprutils@x86_64__old.rpm"
        new = repo_dir / "hyprutils@x86_64__new.rpm"
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
                stage_mock.prune_local_repo(repo_dir)

        remaining_paths = {a["path"] for a in build_db.artifacts(package="hyprutils")}
        assert str(old) not in remaining_paths
        assert str(new) in remaining_paths

    def test_no_duplicates_removes_nothing(self, tmp_path):
        repo_dir = tmp_path / TARGET
        repo_dir.mkdir()
        a = repo_dir / "hyprutils@x86_64__a.rpm"
        b = repo_dir / "hyprutils-devel@x86_64__b.rpm"
        a.write_text("a")
        b.write_text("b")

        fake = _fake_rpm_query(
            {
                ("hyprutils", "x86_64"): "0.14.0-1",
                ("hyprutils-devel", "x86_64"): "0.14.0-1",
            }
        )

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            removed = stage_mock.prune_local_repo(repo_dir)

        assert removed is False
        assert a.exists()
        assert b.exists()

    def test_ignores_src_rpm(self, tmp_path):
        repo_dir = tmp_path / TARGET
        repo_dir.mkdir()
        src = repo_dir / "hyprutils-0.14.0-1.src.rpm"
        src.write_text("src")

        with patch.object(stage_mock, "_rpm_query") as mock_query:
            removed = stage_mock.prune_local_repo(repo_dir)

        mock_query.assert_not_called()
        assert removed is False
        assert src.exists()

    def test_three_versions_keeps_only_newest(self, tmp_path):
        repo_dir = tmp_path / TARGET
        repo_dir.mkdir()
        v1 = repo_dir / "hyprutils@x86_64__v1.rpm"
        v2 = repo_dir / "hyprutils@x86_64__v2.rpm"
        v3 = repo_dir / "hyprutils@x86_64__v3.rpm"
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
            removed = stage_mock.prune_local_repo(repo_dir)

        assert removed is True
        assert not v1.exists()
        assert not v3.exists()
        assert v2.exists()  # 0.14.0-1 is newest

    def test_different_targets_never_compete(self, tmp_path):
        """The concrete bug this layout fixes: an fc43 and an fc44 build of
        the same package used to sit in one shared directory and compete by
        EVR alone (a higher-release fc43 build could beat and delete a
        correct fc44 build). Per-target directories mean prune_local_repo()
        is never even called with both in scope at once."""
        repo_43 = tmp_path / "fedora-43-x86_64"
        repo_44 = tmp_path / "fedora-44-x86_64"
        repo_43.mkdir()
        repo_44.mkdir()
        fc43_rpm = repo_43 / "aquamarine@x86_64__fc43.rpm"
        fc44_rpm = repo_44 / "aquamarine@x86_64__fc44.rpm"
        fc43_rpm.write_text("fc43")
        fc44_rpm.write_text("fc44")

        # fc43's release (10) is numerically higher than fc44's (8) -- exactly
        # the case that let the fc43 build win under the old shared layout.
        def fake(rpm_path: Path, fmt: str) -> str:
            if fmt == "%{NAME}":
                return "aquamarine"
            if fmt == "%{ARCH}":
                return "x86_64"
            if fmt == "%{VERSION}-%{RELEASE}":
                return "0.14.0-10" if "fc43" in rpm_path.name else "0.14.0-8"
            return "0"

        with patch.object(stage_mock, "_rpm_query", side_effect=fake):
            removed_43 = stage_mock.prune_local_repo(repo_43)
            removed_44 = stage_mock.prune_local_repo(repo_44)

        assert removed_43 is False
        assert removed_44 is False
        assert fc43_rpm.exists()
        assert fc44_rpm.exists()


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
    """Test update_local_repo(mock_chroot, repo_dir) copies mock results and
    prunes/regenerates."""

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

        repo_dir = tmp_path / "local-repo" / "fedora-44-x86_64"
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=False):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                copied = stage_mock.update_local_repo("fedora-44-x86_64", repo_dir)

        assert (repo_dir / "hyprutils-0.14.0-1.fc44.x86_64.rpm").exists()
        assert not (repo_dir / "hyprutils-0.14.0-1.fc44.src.rpm").exists()
        mock_regen.assert_called_once_with(repo_dir)
        # Returns the absolute path of the copied (non-src) RPM, for the
        # caller to record as an artifact.
        assert copied == [str(repo_dir / "hyprutils-0.14.0-1.fc44.x86_64.rpm")]

    def test_creates_target_dir_that_does_not_yet_exist(self, tmp_path, monkeypatch):
        """The first build for a brand-new target must not fail just because
        local-repo/<target>/ doesn't exist yet -- mkdir needs parents=True
        since local-repo/ itself may not exist either."""
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-45-x86_64" / "result"
        result_dir.mkdir(parents=True)
        (result_dir / "hyprutils-0.15.0-1.fc45.x86_64.rpm").write_text("rpm")

        repo_dir = tmp_path / "brand-new-local-repo-root" / "fedora-45-x86_64"
        assert not repo_dir.exists()
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=False):
            with patch.object(stage_mock, "regenerate_repo_metadata"):
                copied = stage_mock.update_local_repo("fedora-45-x86_64", repo_dir)

        assert repo_dir.exists()
        assert copied == [str(repo_dir / "hyprutils-0.15.0-1.fc45.x86_64.rpm")]

    def test_regenerates_on_prune_alone(self, tmp_path, monkeypatch):
        """Even with no new RPMs copied, a pruning pass should still trigger
        metadata regeneration (repo content changed)."""
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-44-x86_64" / "result"
        result_dir.mkdir(parents=True)

        repo_dir = tmp_path / "local-repo" / "fedora-44-x86_64"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=True):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                stage_mock.update_local_repo("fedora-44-x86_64", repo_dir)

        mock_regen.assert_called_once_with(repo_dir)

    def test_no_regenerate_when_nothing_changed(self, tmp_path, monkeypatch):
        """No new RPMs and no pruning: metadata is not regenerated."""
        mock_var_lib = tmp_path / "var-lib-mock"
        result_dir = mock_var_lib / "fedora-44-x86_64" / "result"
        result_dir.mkdir(parents=True)

        repo_dir = tmp_path / "local-repo" / "fedora-44-x86_64"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(
            stage_mock, "Path", self._patched_path(tmp_path, mock_var_lib)
        )

        with patch.object(stage_mock, "prune_local_repo", return_value=False):
            with patch.object(stage_mock, "regenerate_repo_metadata") as mock_regen:
                stage_mock.update_local_repo("fedora-44-x86_64", repo_dir)

        mock_regen.assert_not_called()


class TestOfflineGate:
    """TODO-0004: mock invocations disable networking during %build."""

    def test_run_for_package_disables_networking(self, tmp_path):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd", return_value=(True, "", "")) as mock_run_cmd, \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):
            stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed={},
                all_packages={pkg: meta},
                run_id=run_id,
                repo_dir=repo_dir,
            )

        cmd = mock_run_cmd.call_args[0][0]
        assert "--config-opts" in cmd
        assert "rpmbuild_networking=False" in cmd
        assert "use_host_resolv=False" in cmd
        assert str(srpm_path) in cmd

    def test_addrepo_still_added_when_local_repo_has_repodata(self, tmp_path):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        repo_dir = tmp_path / "local-repo" / TARGET
        (repo_dir / "repodata").mkdir(parents=True)

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd", return_value=(True, "", "")) as mock_run_cmd, \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):
            stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed={},
                all_packages={pkg: meta},
                run_id=run_id,
                repo_dir=repo_dir,
            )

        cmd = mock_run_cmd.call_args[0][0]
        assert "--addrepo" in cmd
        assert f"file://{repo_dir}" in cmd
        assert "--config-opts" in cmd


class TestCopyMockResults:
    """copy_mock_results() must not crash the whole pipeline when result_dir
    is corrupted -- a single package's logs failing to copy is a soft
    failure, not a reason to abort every other package in the run."""

    def test_tolerates_result_dir_being_a_file(self, tmp_path, monkeypatch):
        mock_var_lib = tmp_path / "var-lib-mock"
        mock_var_lib.mkdir()
        stray = mock_var_lib / TARGET
        stray.write_bytes(b"stray srpm bytes")  # result_dir's parent is a file

        def fake_path(p, *rest):
            if p == "/var/lib/mock":
                return mock_var_lib
            return Path(p, *rest)

        log_dir = tmp_path / "logs/build/test-pkg"

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "Path", fake_path):
            copied = stage_mock.copy_mock_results(TARGET, "test-pkg")

        assert copied == []


class TestResultDirCleared:
    """TODO-0014: /var/lib/mock is now a persisted volume, not container-
    ephemeral storage -- a stale resultdir from a prior run must not survive
    into the next mock invocation and get misattributed to this package."""

    def test_clears_stale_resultdir_before_running_mock(self, tmp_path, monkeypatch):
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)

        mock_var_lib = tmp_path / "var-lib-mock"
        stale_result = mock_var_lib / TARGET / "result"
        stale_result.mkdir(parents=True)
        (stale_result / "leftover-1.0.0-1.fc44.x86_64.rpm").write_text("stale")

        def fake_path(p, *rest):
            if p == "/var/lib/mock":
                return mock_var_lib
            return Path(p, *rest)

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "Path", fake_path), \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):

            def fake_run_cmd(cmd, log):
                # By the time mock would run, the stale resultdir must already
                # be gone -- otherwise a crash mid-build would leave it for the
                # next run to misattribute.
                assert not stale_result.exists()
                return True, "", ""

            with patch.object(stage_mock, "run_cmd", side_effect=fake_run_cmd):
                stage_mock.run_for_package(
                    pkg,
                    meta,
                    "44",
                    TARGET,
                    proceed=False,
                    failed={},
                    all_packages={pkg: meta},
                    run_id=run_id,
                    repo_dir=repo_dir,
                )

    def test_clears_stale_resultdir_when_it_is_a_file(self, tmp_path, monkeypatch):
        """mock can leave `result` as a plain file instead of a directory (seen
        in practice: the input srpm written straight to that path when the
        resultdir didn't exist yet as a directory). shutil.rmtree() silently
        no-ops on a non-directory even with ignore_errors=True, so this must be
        unlinked explicitly or the corruption persists across every run and
        later crashes copy_mock_results() with NotADirectoryError."""
        pkg = "test-pkg"
        meta = {"version": "1.0.0", "release": 1}
        srpm_path = tmp_path / "test-pkg-1.0.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)

        mock_var_lib = tmp_path / "var-lib-mock"
        stale_result = mock_var_lib / TARGET / "result"
        stale_result.parent.mkdir(parents=True)
        stale_result.write_bytes(b"stray srpm bytes")

        def fake_path(p, *rest):
            if p == "/var/lib/mock":
                return mock_var_lib
            return Path(p, *rest)

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "Path", fake_path), \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):

            def fake_run_cmd(cmd, log):
                assert not stale_result.exists()
                return True, "", ""

            with patch.object(stage_mock, "run_cmd", side_effect=fake_run_cmd):
                stage_mock.run_for_package(
                    pkg,
                    meta,
                    "44",
                    TARGET,
                    proceed=False,
                    failed={},
                    all_packages={pkg: meta},
                    run_id=run_id,
                    repo_dir=repo_dir,
                )


class TestWarnIfFlatLocalRepo:
    """A pre-2026-08-11 checkout can have flat RPMs directly under
    local-repo/ (no chroot subdirectory) left over from before per-target
    scoping. They are not served to mock any more -- warn, never delete."""

    def test_warns_when_flat_rpms_present(self, tmp_path, caplog):
        local_repo_root = tmp_path / "local-repo"
        local_repo_root.mkdir()
        (local_repo_root / "aquamarine-0.14.0-10.fc43.x86_64.rpm").write_text("rpm")

        with caplog.at_level("WARNING"):
            stage_mock.warn_if_flat_local_repo(local_repo_root)

        assert any("local-repo" in r.message for r in caplog.records)
        # Never deletes -- warning only.
        assert (local_repo_root / "aquamarine-0.14.0-10.fc43.x86_64.rpm").exists()

    def test_no_warning_when_only_scoped_dirs_present(self, tmp_path, caplog):
        local_repo_root = tmp_path / "local-repo"
        (local_repo_root / TARGET).mkdir(parents=True)
        (local_repo_root / TARGET / "aquamarine-0.14.0-8.fc44.x86_64.rpm").write_text("rpm")

        with caplog.at_level("WARNING"):
            stage_mock.warn_if_flat_local_repo(local_repo_root)

        assert caplog.records == []

    def test_no_warning_when_root_does_not_exist(self, tmp_path, caplog):
        local_repo_root = tmp_path / "local-repo"
        with caplog.at_level("WARNING"):
            stage_mock.warn_if_flat_local_repo(local_repo_root)
        assert caplog.records == []


class TestPreflight:
    """run_for_package() runs the repo_preflight check before spawning mock
    at all -- a missing/wrong-chroot local dependency must fail fast with a
    `preflight:`-prefixed reason instead of paying for a full mock invocation
    that dnf5 would fail anyway."""

    def _setup(self, tmp_path, pkg="hyprland", depends_on=None):
        meta = {"version": "0.51.0", "release": 1}
        if depends_on is not None:
            meta["depends_on"] = depends_on
        srpm_path = tmp_path / f"{pkg}-0.51.0-1.fc44.src.rpm"
        srpm_path.write_bytes(b"srpm")
        run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
        build_db.set_stage(pkg, "srpm", TARGET, run_id, "success", path=str(srpm_path))
        log_dir = tmp_path / "logs/build" / pkg
        log_dir.mkdir(parents=True)
        return meta, run_id, log_dir

    def test_preflight_error_blocks_before_mock_runs(self, tmp_path, monkeypatch):
        pkg = "hyprland"
        meta, run_id, log_dir = self._setup(tmp_path, pkg, depends_on=["aquamarine"])
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)  # empty -- aquamarine is missing
        all_packages = {pkg: meta, "aquamarine": {"version": "0.14.0", "release": 8}}

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd") as mock_run_cmd:
            ok = stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed={},
                all_packages=all_packages,
                run_id=run_id,
                repo_dir=repo_dir,
            )

        mock_run_cmd.assert_not_called()
        assert ok is False
        entry = build_db.get_stage(pkg, "mock", TARGET)
        assert entry["state"] == "failed"
        assert entry["reason"].startswith("preflight:")

    def test_skip_repo_preflight_env_demotes_to_warning(self, tmp_path, monkeypatch):
        pkg = "hyprland"
        meta, run_id, log_dir = self._setup(tmp_path, pkg, depends_on=["aquamarine"])
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)
        all_packages = {pkg: meta, "aquamarine": {"version": "0.14.0", "release": 8}}
        monkeypatch.setenv("SKIP_REPO_PREFLIGHT", "1")

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd", return_value=(True, "", "")) as mock_run_cmd, \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):
            stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed={},
                all_packages=all_packages,
                run_id=run_id,
                repo_dir=repo_dir,
            )

        mock_run_cmd.assert_called_once()

    def test_no_local_deps_proceeds_normally(self, tmp_path):
        pkg = "standalone"
        meta, run_id, log_dir = self._setup(tmp_path, pkg)
        repo_dir = tmp_path / "local-repo" / TARGET
        repo_dir.mkdir(parents=True)

        with patch.object(stage_mock, "get_package_log_dir", return_value=log_dir), \
             patch.object(stage_mock, "ROOT", tmp_path), \
             patch.object(stage_mock, "run_cmd", return_value=(True, "", "")) as mock_run_cmd, \
             patch.object(stage_mock, "copy_mock_results", return_value=[]), \
             patch.object(stage_mock, "update_local_repo", return_value=[]):
            ok = stage_mock.run_for_package(
                pkg,
                meta,
                "44",
                TARGET,
                proceed=False,
                failed={},
                all_packages={pkg: meta},
                run_id=run_id,
                repo_dir=repo_dir,
            )

        mock_run_cmd.assert_called_once()
        assert ok is True
