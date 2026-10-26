"""Tests for scripts/gotify-notify.py (#COPR-0026)."""

import importlib
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import build_db, paths as paths_module

gn = importlib.import_module("gotify-notify")


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_module, "BUILD_DB", tmp_path / "build-report.db")
    monkeypatch.setattr(gn, "LOG_DIR", tmp_path)
    yield
    build_db.close()


class TestFormatSummary:
    def test_updates_and_errors(self):
        out = gn.format_summary(
            {"foo": ("1.1.1", "1.1.2"), "baz": ("2.0", "2.1")},
            checked=3,
            succeeded=2,
            errors=["bar"],
        )
        assert out == (
            "updated 2: baz 2.0>2.1, foo 1.1.1>1.1.2. checked: 3, succeeded: 2, "
            "errors: bar"
        )

    def test_nothing_updated_no_errors(self):
        out = gn.format_summary({}, checked=0, succeeded=0, errors=[])
        assert out == "updated 0. checked: 0, succeeded: 0, errors: none"


class TestBuildSummary:
    def _run(self, started_at_offset=0):
        return build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")

    def test_counts_packages_in_window_only(self, tmp_path):
        old = self._run()
        build_db.set_stage("old-pkg", "mock", "fedora-43-x86_64", old, "failed")
        conn = build_db.connect()
        conn.execute("UPDATE runs SET started_at = started_at - 1000")
        conn.commit()
        since = build_db.now_epoch() - 10
        new = self._run()
        build_db.set_stage("ok", "mock", "fedora-43-x86_64", new, "success")
        build_db.set_stage("bad", "mock", "fedora-43-x86_64", new, "failed")
        build_db.set_stage("bad", "mock", "fedora-44-x86_64", new, "success")
        checked, succeeded, errors = gn.build_run_counts(since)
        assert (checked, succeeded, errors) == (2, 1, ["bad"])

    def test_missing_db_rows_gives_zeroes(self):
        assert gn.build_run_counts(0) == (0, 0, [])


class TestSend:
    def test_request_shape(self):
        resp = MagicMock()
        with patch.object(gn.urllib.request, "urlopen", return_value=resp) as m:
            ok = gn.send("https://g.example/", "TOK", "t", "m", 7)
        assert ok is True
        req = m.call_args.args[0]
        assert req.full_url == "https://g.example/message"
        assert req.get_header("X-gotify-key") == "TOK"
        assert "TOK" not in req.full_url
        assert json.loads(req.data) == {"title": "t", "message": "m", "priority": 7}
        assert m.call_args.kwargs["timeout"] == 10

    def test_url_error_warns_and_returns_false(self, capsys):
        with patch.object(
            gn.urllib.request, "urlopen", side_effect=urllib.error.URLError("down")
        ):
            assert gn.send("https://g.example", "TOK", "t", "m", 5) is False
        assert "warning" in capsys.readouterr().err

    @pytest.mark.parametrize("url", ["gotify.example.org", "", "ftp//x", "://x"])
    def test_malformed_url_warns_and_returns_false(self, url, capsys):
        """A URL urllib rejects (no scheme) is a warning, not a traceback."""
        assert gn.send(url, "TOK", "t", "m", 5) is False
        assert "warning" in capsys.readouterr().err

    def test_main_with_schemeless_url_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setenv("GOTIFY_URL", "gotify.example.org")
        monkeypatch.setenv("GOTIFY_TOKEN", "TOK")
        assert gn.main(["--title", "t", "--message", "m"]) == 0
        assert "warning" in capsys.readouterr().err

    def test_missing_config_skips_without_request(self, monkeypatch, capsys):
        monkeypatch.delenv("GOTIFY_URL", raising=False)
        monkeypatch.delenv("GOTIFY_TOKEN", raising=False)
        with patch.object(gn.urllib.request, "urlopen") as m:
            assert gn.main(["--title", "t", "--message", "m"]) == 0
        m.assert_not_called()
        assert "GOTIFY_URL" in capsys.readouterr().err


class TestMain:
    def test_summary_mode_reads_sentinels_and_sets_priority(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("GOTIFY_URL", "https://g.example")
        monkeypatch.setenv("GOTIFY_TOKEN", "TOK")
        (tmp_path / ".update-versions-changes.json").write_text(
            json.dumps({"foo": ["1.1.1", "1.1.2"]})
        )
        (tmp_path / ".update-daily-started").write_text("0\n")
        run = build_db.start_run("fedora-43-x86_64", "fedora", "43", "x86_64")
        build_db.set_stage("bar", "mock", "fedora-43-x86_64", run, "failed")
        with patch.object(gn, "send", return_value=True) as m:
            assert gn.main(["--summary"]) == 0
        _, _, title, message, priority = m.call_args.args
        assert title == "hyprland-copr update-daily"
        assert message == (
            "updated 1: foo 1.1.1>1.1.2. checked: 1, succeeded: 0, errors: bar"
        )
        assert priority == 8

    def test_send_failure_still_exits_zero(self, monkeypatch):
        monkeypatch.setenv("GOTIFY_URL", "https://g.example")
        monkeypatch.setenv("GOTIFY_TOKEN", "TOK")
        with patch.object(gn, "send", return_value=False):
            assert gn.main(["--title", "t", "--message", "m"]) == 0
