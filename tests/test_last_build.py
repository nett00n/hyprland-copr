"""Tests for scripts/last-build.py (#COPR-0028)."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths as paths_module

lb = importlib.import_module("last-build")

T43 = "fedora-43-x86_64"
T44 = "fedora-44-x86_64"
HOUR = 3600


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_module, "BUILD_DB", tmp_path / "build-report.db")
    monkeypatch.setattr(lb, "ROOT", tmp_path)
    yield
    build_db.close()


def _run(target, started, duration=60, exit_state="ok", package_filter=""):
    run_id = build_db.start_run(
        target, "fedora", target.split("-")[1], "x86_64", package_filter=package_filter
    )
    conn = build_db.connect()
    conn.execute(
        "UPDATE runs SET started_at = ?, completed_at = ?, exit_state = ? WHERE id = ?",
        (started, started + duration, exit_state, run_id),
    )
    conn.commit()
    return run_id


def _stage(pkg, stage, target, run_id, state, started=1000, took=5, **fields):
    build_db.set_stage(
        pkg,
        stage,
        target,
        run_id,
        state,
        started_at=started,
        completed_at=started + took,
        **fields,
    )


class TestNightRuns:
    def test_empty_db(self):
        assert lb.night_runs(12) == []

    def test_window_is_relative_to_newest_run(self):
        now = 1_000_000
        old = _run(T43, now - 20 * HOUR)
        a = _run(T43, now - 2 * HOUR)
        b = _run(T44, now)
        ids = [r["id"] for r in lb.night_runs(12)]
        assert old not in ids
        assert ids == [a, b]

    def test_hours_widens_window(self):
        now = 1_000_000
        old = _run(T43, now - 20 * HOUR)
        _run(T44, now)
        assert old in [r["id"] for r in lb.night_runs(24)]


class TestLatestRows:
    def test_failure_fixed_by_later_run_is_dropped(self):
        now = 1_000_000
        r1 = _run(T44, now - HOUR, exit_state="failed")
        r2 = _run(T44, now)
        _stage("foo", "mock", T44, r1, "failed")
        _stage("foo", "mock", T44, r2, "success")
        rows = lb.latest_rows([r1, r2])
        assert [(r["package"], r["state"]) for r in rows] == [("foo", "success")]

    def test_failure_not_retried_stays(self):
        now = 1_000_000
        r1 = _run(T44, now - HOUR, exit_state="failed")
        r2 = _run(T44, now, package_filter="other")
        _stage("foo", "mock", T44, r1, "failed")
        _stage("other", "mock", T44, r2, "success")
        states = {r["package"]: r["state"] for r in lb.latest_rows([r1, r2])}
        assert states == {"foo": "failed", "other": "success"}


class TestCountsAndSlowest:
    def _rows(self):
        r = _run(T44, 1_000_000)
        _stage("a", "mock", T44, r, "success", took=100)
        _stage("b", "mock", T44, r, "failed", took=30)
        _stage("c", "mock", T44, r, "skipped", took=1)
        _stage("a", "srpm", T44, r, "success", took=500)
        return lb.latest_rows([r])

    def test_stage_counts(self):
        counts = lb.stage_counts(self._rows())
        assert counts[(T44, "mock")] == {"success": 1, "failed": 1, "skipped": 1}
        assert counts[(T44, "srpm")] == {"success": 1}

    def test_slowest_orders_by_duration(self):
        top = lb.slowest(self._rows(), 2)
        assert [(r["package"], r["stage"]) for r in top] == [
            ("a", "srpm"),
            ("a", "mock"),
        ]


class TestFailureExcerpt:
    def _row(self, log):
        return {"stage": "mock", "log": str(log)}

    def test_caps_at_20_lines_and_links_first_issue(self, tmp_path):
        d = tmp_path / "logs" / "runs" / "1" / T44 / "foo"
        d.mkdir(parents=True)
        log = d / "20-mock.log"
        log.write_text(
            "\n".join(f"No match for argument: libfoo{i}-devel" for i in range(40))
        )
        lines, link = lb.failure_excerpt(self._row(log))
        assert 0 < len(lines) <= 20
        assert link.startswith(str(log)) and link.rsplit(":", 1)[1].isdigit()

    def test_falls_back_to_error_lines(self, tmp_path):
        log = tmp_path / "20-mock.log"
        log.write_text("start\nsome noise\nERROR: boom happened\nend\n")
        lines, link = lb.failure_excerpt(self._row(log))
        assert any("boom happened" in line for line in lines)
        assert link == str(log)

    def test_falls_back_to_log_tail(self, tmp_path):
        log = tmp_path / "20-mock.log"
        log.write_text("\n".join(f"line {i}" for i in range(50)))
        lines, _ = lb.failure_excerpt(self._row(log))
        assert len(lines) == 20 and lines[-1] == "line 49"

    def test_pruned_log(self, tmp_path):
        log = tmp_path / "gone.log"
        lines, link = lb.failure_excerpt(self._row(log))
        assert lines == [f"log pruned: {log}"]
        assert link == str(log)

    def test_relative_log_resolves_against_root(self, tmp_path):
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "x.log").write_text("ERROR: relative ok\n")
        lines, link = lb.failure_excerpt({"stage": "mock", "log": "logs/x.log"})
        assert any("relative ok" in line for line in lines)
        assert link == "logs/x.log"


class TestRender:
    def _setup(self, tmp_path):
        log = tmp_path / "20-mock.log"
        log.write_text("ERROR: kaboom\n")
        r = _run(T44, 1_000_000, exit_state="failed")
        _stage(
            "foo", "mock", T44, r, "failed", version="1.0", reason="prior-failed",
            log=str(log), build_id=7,
        )
        _stage("bar", "mock", T44, r, "success")
        return log

    def test_empty(self):
        assert lb.render(12, None, None, "text") == "no runs found\n"

    def test_text_report_sections(self, tmp_path):
        log = self._setup(tmp_path)
        out = lb.render(12, None, None, "text")
        for section in ("Runs", "Stage counts", "Slowest stages", "Failures"):
            assert section in out
        assert "foo" in out and "prior-failed" in out and "kaboom" in out
        assert str(log) in out

    def test_markdown_links_log(self, tmp_path):
        log = self._setup(tmp_path)
        out = lb.render(12, None, None, "md")
        assert f"]({log}" in out

    def test_package_filter(self, tmp_path):
        self._setup(tmp_path)
        out = lb.render(12, "bar", None, "text")
        assert "foo" not in out.split("Failures")[-1]

    def test_target_filter_hides_other_targets(self, tmp_path):
        self._setup(tmp_path)
        out = lb.render(12, None, T43, "text")
        assert T44 not in out.split("Stage counts")[-1]


class TestAutohealSection:
    """#COPR-0029: rows whose reason starts with "autoheal:" get their own section."""

    def test_healed_and_gave_up_rows_are_listed(self):
        run = _run(T44, 1_000_000)
        _stage(
            "Hyprland", "mock", T44, run, "success",
            reason="autoheal: +pkgconfig(libcanberra) (1 cycle)",
        )
        _stage(
            "ironbar", "mock", T44, run, "failed",
            reason="autoheal: gave up after 10 cycles (+pkgconfig(a))",
        )
        _stage("other", "mock", T44, run, "success", reason="changed")
        out = lb.render(12, None, None, "text")
        assert "## Autohealed (2)" in out
        assert (
            "- Hyprland mock fedora-44-x86_64 success: "
            "autoheal: +pkgconfig(libcanberra) (1 cycle)"
        ) in out
        assert "- ironbar mock fedora-44-x86_64 failed: autoheal: gave up" in out
        assert "- other mock" not in out.split("## Autohealed")[1].split("## Failures")[0]

    def test_no_section_without_autoheal(self):
        run = _run(T44, 1_000_000)
        _stage("foo", "mock", T44, run, "success", reason="changed")
        assert "Autohealed" not in lb.render(12, None, None, "text")
