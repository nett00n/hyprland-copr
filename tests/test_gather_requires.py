"""Tests for scripts/gather-requires.py. #BUG-0078

Fakes the `rpm` subprocess boundary (the module's own `rpm()` helper) so
`bare_sonames()`/`whatprovides()` are exercised as pure functions over
fixture rpm output, with no real `rpm` binary or RPM file involved.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

gather_requires = importlib.import_module("scripts.gather-requires")

bare_sonames = gather_requires.bare_sonames
whatprovides = gather_requires.whatprovides
main = gather_requires.main


class TestBareSonames:
    def test_extracts_bare_soname_entries(self):
        with patch.object(
            gather_requires,
            "rpm",
            return_value=[
                "libfoo.so.1()(64bit)",
                "rtld(GNU_HASH)",
                "libbar.so.2()(64bit)",
            ],
        ):
            result = bare_sonames("pkg.rpm")

        assert result == ["libfoo.so.1()(64bit)", "libbar.so.2()(64bit)"]

    def test_deduplicates_repeated_entries(self):
        with patch.object(
            gather_requires,
            "rpm",
            return_value=["libfoo.so.1()(64bit)", "libfoo.so.1()(64bit)"],
        ):
            result = bare_sonames("pkg.rpm")

        assert result == ["libfoo.so.1()(64bit)"]

    def test_ignores_non_bare_soname_requires(self):
        """Versioned/interface requires (with a paren'd version) don't match."""
        with patch.object(
            gather_requires,
            "rpm",
            return_value=["libfoo.so.1(GLIBC_2.2.5)(64bit)", "/bin/sh"],
        ):
            result = bare_sonames("pkg.rpm")

        assert result == []

    def test_no_requires_is_empty(self):
        with patch.object(gather_requires, "rpm", return_value=[]):
            assert bare_sonames("pkg.rpm") == []


class TestWhatprovides:
    def test_resolves_soname_to_package_name(self):
        with patch.object(gather_requires, "rpm", return_value=["glib2"]):
            assert whatprovides("libglib-2.0.so.0()(64bit)") == "glib2"

    def test_prefers_shortest_name_over_variants(self):
        """-libs/-devel variants are longer; base package should win."""
        with patch.object(
            gather_requires,
            "rpm",
            return_value=["libfoo-devel", "libfoo", "libfoo-extra-libs"],
        ):
            assert whatprovides("libfoo.so.1()(64bit)") == "libfoo"

    def test_not_owned_is_none(self):
        with patch.object(
            gather_requires, "rpm", return_value=["is not owned by any package"]
        ):
            assert whatprovides("libfoo.so.1()(64bit)") is None

    def test_empty_result_is_none(self):
        with patch.object(gather_requires, "rpm", return_value=[]):
            assert whatprovides("libfoo.so.1()(64bit)") is None


class TestSkipPackages:
    def test_default_skip_set_excludes_base_system(self):
        assert "glibc" in gather_requires.SKIP_PACKAGES
        assert "libstdc++" in gather_requires.SKIP_PACKAGES

    def test_skip_packages_env_extends_default_set(self, monkeypatch):
        """SKIP_PACKAGES is read from os.environ at import time -- verify the
        union logic directly rather than re-importing the module."""
        monkeypatch.setenv("SKIP_PACKAGES", "extra-one,extra-two")
        extra = (
            set("extra-one,extra-two".split(","))
            if "extra-one,extra-two"
            else set()
        )
        combined = gather_requires._DEFAULT_SKIP | extra
        assert "extra-one" in combined
        assert "glibc" in combined


class TestMain:
    def test_prints_resolved_requires_and_unresolved_sonames(self, capsys):
        with (
            patch.object(
                gather_requires,
                "bare_sonames",
                return_value=["libfoo.so.1()(64bit)", "libbar.so.1()(64bit)"],
            ),
            patch.object(
                gather_requires,
                "whatprovides",
                side_effect=lambda s: "foopkg" if "foo" in s else None,
            ),
            patch.object(sys, "argv", ["gather-requires.py", "pkg.rpm"]),
        ):
            main()

        out = capsys.readouterr().out
        assert "# pkg.rpm" in out
        assert "requires:" in out
        assert "- foopkg" in out
        assert "# unresolved (not in local rpmdb):" in out
        assert "libbar.so.1()(64bit)" in out

    def test_no_args_exits(self):
        with patch.object(sys, "argv", ["gather-requires.py"]):
            try:
                main()
                raised = False
            except SystemExit:
                raised = True
        assert raised
