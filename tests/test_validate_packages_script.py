"""Tests for scripts/validate-packages.py (the pre-commit gate).

Covers the new url/.gitmodules resolution warning added alongside the
BUG-0013 fix -- collect_gitmodules_urls()/validate_submodule_urls() mirror
update-versions.py's exact-match `url_to_module` lookup so a mismatch (a
stray or missing trailing ".git") is visible before commit, not silently
discovered weeks later. The rest of this script (self-dependency /
depends_on / ignore=dirty checks) had zero prior test coverage
(docs/todo.md TODO-0041); not expanding that here, only testing the delta.
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

validate_packages = importlib.import_module("scripts.validate-packages")


class TestCollectGitmodulesUrls:
    def test_collects_all_submodule_urls(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gitmodules").write_text(
            '[submodule "submodules/org/a"]\n'
            "\tpath = submodules/org/a\n"
            "\turl = https://github.com/org/a\n"
            '[submodule "submodules/org/b"]\n'
            "\tpath = submodules/org/b\n"
            "\turl = https://github.com/org/b.git\n"
        )

        urls = validate_packages.collect_gitmodules_urls()

        assert urls == {"https://github.com/org/a", "https://github.com/org/b.git"}

    def test_missing_gitmodules_returns_empty_set(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        assert validate_packages.collect_gitmodules_urls() == set()


class TestValidateSubmoduleUrls:
    def test_matching_url_produces_no_warning(self):
        packages = {"pkg-a": {"url": "https://github.com/org/a"}}
        gitmodules_urls = {"https://github.com/org/a"}

        warnings = validate_packages.validate_submodule_urls(packages, gitmodules_urls)

        assert warnings == []

    def test_mismatched_url_warns(self):
        """Regression case: Waybar-git's url was missing .git that .gitmodules had."""
        packages = {"Waybar-git": {"url": "https://github.com/Alexays/Waybar"}}
        gitmodules_urls = {"https://github.com/Alexays/Waybar.git"}

        warnings = validate_packages.validate_submodule_urls(packages, gitmodules_urls)

        assert len(warnings) == 1
        assert "Waybar-git" in warnings[0]

    def test_missing_url_ignored(self):
        packages = {"pkg-a": {}}
        gitmodules_urls = {"https://github.com/org/a"}

        warnings = validate_packages.validate_submodule_urls(packages, gitmodules_urls)

        assert warnings == []


class TestMainWiring:
    """Confirm main() surfaces url mismatches as warnings, not commit-blocking errors."""

    def _write_repo(self, tmp_path, pkg_url, gitmodules_url):
        (tmp_path / "packages.yaml").write_text(
            f"pkg-a:\n  url: {pkg_url}\n  depends_on: []\n"
        )
        (tmp_path / ".gitmodules").write_text(
            '[submodule "submodules/org/a"]\n'
            "\tpath = submodules/org/a\n"
            f"\turl = {gitmodules_url}\n"
            "\tignore = dirty\n"
        )

    def test_url_mismatch_warns_but_does_not_exit(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        self._write_repo(
            tmp_path,
            pkg_url="https://github.com/org/a",
            gitmodules_url="https://github.com/org/a.git",
        )

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "pkg-a" in captured.err
        assert "✓ packages.yaml validation passed" in captured.out

    def test_matching_url_prints_no_warning(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        self._write_repo(
            tmp_path,
            pkg_url="https://github.com/org/a",
            gitmodules_url="https://github.com/org/a",
        )

        validate_packages.main()

        captured = capsys.readouterr()
        assert "don't match .gitmodules" not in captured.err
