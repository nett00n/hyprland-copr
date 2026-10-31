"""Tests for the autoheal hook in scripts/stage-mock.py (#COPR-0029): a failed mock
build is healed via lib.deps_autoheal.heal_loop and the stage row records the outcome."""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths
from lib.deps_autoheal import HealResult

stage_mock = importlib.import_module("scripts.stage-mock")

TARGET = "fedora-44-x86_64"
META = {"version": "1.0", "release": 1}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD_DB", tmp_path / "build-report.db")
    monkeypatch.setattr(paths, "RUNS_LOG_DIR", tmp_path / "logs" / "runs")
    monkeypatch.setattr(stage_mock, "ROOT", tmp_path)
    monkeypatch.delenv("AUTOHEAL", raising=False)
    monkeypatch.delenv("AUTOHEAL_MAX_CYCLES", raising=False)
    build_db.close()
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    assert run_id == 1
    srpm = tmp_path / "pkg-1.0-1.src.rpm"
    srpm.write_text("srpm")
    build_db.set_stage("pkg", "srpm", TARGET, run_id, "success", path=str(srpm))
    with (
        patch.object(stage_mock, "check_buildroot_repo", return_value=([], [])),
        patch.object(stage_mock, "update_local_repo", return_value=[]),
    ):
        yield tmp_path
    build_db.close()


def _run(tmp_path):
    failed: dict = {}
    ok = stage_mock.run_for_package(
        "pkg", META, "44", TARGET, False, failed, {"pkg": META}, 1, tmp_path / "repo"
    )
    return ok, failed, build_db.get_stage("pkg", "mock", TARGET)


def test_healed_build_is_a_success_with_the_heal_reason(env):
    result = HealResult(True, 1, ["pkgconfig(x)"], "autoheal: +pkgconfig(x) (1 cycle)")
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(stage_mock, "heal_loop", return_value=result) as heal,
    ):
        ok, failed, row = _run(env)
    assert ok is True and failed["pkg"] is False
    assert row["state"] == "success"
    assert row["reason"] == "autoheal: +pkgconfig(x) (1 cycle)"
    heal.assert_called_once()
    assert heal.call_args.kwargs["limit"] == 10
    assert heal.call_args.kwargs["fedora_version"] == "44"


def test_exhausted_cycles_fail_the_stage(env):
    reason = "autoheal: gave up after 3 cycles (+pkgconfig(a), +pkgconfig(b))"
    result = HealResult(False, 3, ["pkgconfig(a)", "pkgconfig(b)"], reason)
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(stage_mock, "heal_loop", return_value=result),
    ):
        ok, failed, row = _run(env)
    assert ok is False and failed["pkg"] is True
    assert row["state"] == "failed" and row["reason"] == reason


def test_the_file_list_vote_gets_every_supported_chroot(env):
    """#COPR-0029: removals need all chroots, so heal_loop is told which ones."""
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(
            stage_mock, "heal_loop", return_value=HealResult(False, 0, [], "")
        ) as heal,
    ):
        _run(env)
    kwargs = heal.call_args.kwargs
    assert kwargs["target"] == TARGET
    assert kwargs["version"] == "1.0"
    assert kwargs["targets"] == [
        "fedora-43-x86_64",
        "fedora-44-x86_64",
        "fedora-45-x86_64",
    ]
    assert kwargs["get_stage"] is build_db.get_stage


def test_a_pending_vote_leaves_a_failed_row_without_a_rebuild(env):
    reason = (
        "autoheal: pending -files:%{_bindir}/x "
        "(needs all chroots; lacking on 1/3: fedora-44-x86_64)"
    )
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False) as mock_once,
        patch.object(
            stage_mock, "heal_loop", return_value=HealResult(False, 0, [], reason)
        ),
    ):
        ok, failed, row = _run(env)
    assert ok is False and failed["pkg"] is True
    assert row["state"] == "failed" and row["reason"] == reason
    mock_once.assert_called_once()  # the original build only


def test_limit_comes_from_environment(env, monkeypatch):
    monkeypatch.setenv("AUTOHEAL_MAX_CYCLES", "3")
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(
            stage_mock, "heal_loop", return_value=HealResult(False, 0, [], "")
        ) as heal,
    ):
        _run(env)
    assert heal.call_args.kwargs["limit"] == 3


def test_nothing_healed_leaves_a_plain_failure(env):
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(stage_mock, "heal_loop", return_value=HealResult(False, 0, [], "")),
    ):
        ok, failed, row = _run(env)
    assert ok is False and failed["pkg"] is True
    assert row["state"] == "failed" and not row.get("reason")


def test_autoheal_off_skips_the_loop(env, monkeypatch):
    monkeypatch.setenv("AUTOHEAL", "false")
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=False),
        patch.object(stage_mock, "heal_loop") as heal,
    ):
        ok, _, row = _run(env)
    assert ok is False and row["state"] == "failed"
    heal.assert_not_called()


def test_successful_build_never_heals(env):
    with (
        patch.object(stage_mock, "_run_mock_once", return_value=True),
        patch.object(stage_mock, "heal_loop") as heal,
    ):
        ok, _, row = _run(env)
    assert ok is True and row["state"] == "success"
    heal.assert_not_called()


def test_rebuild_regenerates_spec_and_srpm_before_mock(env):
    """_rebuild_healed re-reads packages.yaml, reruns spec then srpm, then mock
    with the freshly built SRPM."""
    order: list[str] = []
    spec, srpm = MagicMock(), MagicMock()
    spec.run_for_package.side_effect = lambda *a: order.append("spec") or True

    def fake_srpm(*a):
        order.append("srpm")
        build_db.set_stage("pkg", "srpm", TARGET, 1, "success", path="/new.src.rpm")
        return True

    srpm.run_for_package.side_effect = fake_srpm
    stages = {"stage-spec": spec, "stage-srpm": srpm}
    with (
        patch.object(stage_mock, "get_packages", return_value={"pkg": META}),
        patch.object(
            stage_mock.importlib, "import_module", side_effect=lambda n: stages[n]
        ),
        patch.object(stage_mock, "_run_mock_once", return_value=True) as mock_once,
    ):
        ok = stage_mock._rebuild_healed(
            "pkg", "44", TARGET, 1, env / "repo", env / "20-mock.log"
        )
    assert ok is True and order == ["spec", "srpm"]
    assert mock_once.call_args.args[0][-1] == "/new.src.rpm"
    # version comes from the reloaded entry, not from the first attempt
    assert mock_once.call_args.args[-1] == "1.0-1.fc44"


def test_rebuild_stops_when_spec_generation_fails(env):
    spec, srpm = MagicMock(), MagicMock()
    spec.run_for_package.return_value = False
    stages = {"stage-spec": spec, "stage-srpm": srpm}
    with (
        patch.object(stage_mock, "get_packages", return_value={"pkg": META}),
        patch.object(
            stage_mock.importlib, "import_module", side_effect=lambda n: stages[n]
        ),
        patch.object(stage_mock, "_run_mock_once") as mock_once,
    ):
        ok = stage_mock._rebuild_healed(
            "pkg", "44", TARGET, 1, env / "repo", env / "20-mock.log"
        )
    assert ok is False
    srpm.run_for_package.assert_not_called()
    mock_once.assert_not_called()


class TestRehashAfterAutoheal:
    """full-cycle re-stamps the cache hashes after stage-mock edited packages.yaml,
    so the healed spec is a cache hit next run instead of a rebuild."""

    def test_replaces_meta_and_restamps_cached_stages(self, env):
        full_cycle = importlib.import_module("scripts.full-cycle")
        fresh = {"version": "1.0", "build_requires": ["pkgconfig(x)"]}
        packages = {"pkg": dict(META)}
        all_packages = {"pkg": dict(META)}
        for stage in ("spec", "srpm"):
            build_db.set_stage("pkg", stage, TARGET, 1, "success")
        with (
            patch.object(full_cycle, "get_packages", return_value={"pkg": fresh}),
            patch.object(
                full_cycle, "compute_input_hashes", return_value={"content": "new"}
            ) as hashes,
        ):
            result = full_cycle.rehash_after_autoheal(
                "pkg", TARGET, packages, all_packages
            )
        assert result == {"content": "new"}
        assert packages["pkg"] is fresh and all_packages["pkg"] is fresh
        hashes.assert_called_once_with("pkg", fresh, all_packages)
        for stage in ("spec", "srpm"):
            stored = build_db.get_stage("pkg", stage, TARGET)["hashes"]
            assert stored == {"content": "new"}
