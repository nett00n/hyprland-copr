"""preflight_autoheal's upstream-mirror auto-fetch (#COPR-0004)."""

import importlib
from unittest.mock import patch

from lib import paths

full_cycle = importlib.import_module("scripts.full-cycle")

PACKAGES = {
    "a": {"url": "https://github.com/org/a"},
    "b": {"url": "https://github.com/org/b"},
}


def _run(monkeypatch, tmp_path, fetch_result=None):
    monkeypatch.setattr(paths, "UPSTREAM_DIR", tmp_path / ".cache" / "upstream")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    with (
        patch.object(full_cycle, "missing_entries", return_value=[]),
        patch.object(full_cycle, "fetch_mirror", return_value=fetch_result) as fetch,
    ):
        full_cycle.preflight_autoheal(PACKAGES)
    return fetch


def test_fetches_every_uncached_mirror(monkeypatch, tmp_path, capsys):
    fetch = _run(monkeypatch, tmp_path)
    assert [c.args[0] for c in fetch.call_args_list] == [
        "https://github.com/org/a",
        "https://github.com/org/b",
    ]
    assert "Auto-fetched upstream mirrors: org/a, org/b" in capsys.readouterr().out


def test_skips_mirrors_that_already_exist(monkeypatch, tmp_path):
    (tmp_path / ".cache" / "upstream" / "org" / "a.git").mkdir(parents=True)
    fetch = _run(monkeypatch, tmp_path)
    assert [c.args[0] for c in fetch.call_args_list] == ["https://github.com/org/b"]


def test_fetch_failure_warns_and_continues(monkeypatch, tmp_path, capsys):
    _run(monkeypatch, tmp_path, fetch_result="network down")
    out = capsys.readouterr().out
    assert "could not fetch upstream org/a: network down" in out
    assert "Auto-fetched" not in out
