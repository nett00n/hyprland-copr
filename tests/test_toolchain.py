"""Tests for lib.toolchain (docs/todo.md TODO-0007)."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.toolchain import (
    chroot_package_version,
    compare_versions,
    go_toolchain_skew,
    parse_go_toolchain_directive,
    parse_rust_version_directive,
    rust_toolchain_skew,
)


class TestParseGoToolchainDirective:
    def test_reads_toolchain_line(self, tmp_path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/foo\n\ngo 1.21\n\ntoolchain go1.22.3\n")
        assert parse_go_toolchain_directive(go_mod) == "1.22.3"

    def test_falls_back_to_go_directive(self, tmp_path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/foo\n\ngo 1.21\n")
        assert parse_go_toolchain_directive(go_mod) == "1.21"

    def test_missing_file(self, tmp_path):
        assert parse_go_toolchain_directive(tmp_path / "go.mod") is None

    def test_no_directive(self, tmp_path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/foo\n")
        assert parse_go_toolchain_directive(go_mod) is None


class TestParseRustVersionDirective:
    def test_reads_rust_version(self, tmp_path):
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "foo"\nrust-version = "1.75"\n')
        assert parse_rust_version_directive(cargo_toml) == "1.75"

    def test_missing_field(self, tmp_path):
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "foo"\n')
        assert parse_rust_version_directive(cargo_toml) is None

    def test_missing_file(self, tmp_path):
        assert parse_rust_version_directive(tmp_path / "Cargo.toml") is None

    def test_malformed_toml(self, tmp_path):
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text("not valid toml [[[")
        assert parse_rust_version_directive(cargo_toml) is None


class TestCompareVersions:
    def test_equal(self):
        assert compare_versions("1.22.0", "1.22.0") == 0

    def test_less_than(self):
        assert compare_versions("1.21.0", "1.22.0") == -1

    def test_greater_than(self):
        assert compare_versions("1.23.0", "1.22.0") == 1

    def test_different_lengths_equal_prefix(self):
        assert compare_versions("1.22", "1.22.0") == 0

    def test_different_lengths_shorter_is_older(self):
        assert compare_versions("1.22", "1.22.3") == -1


class TestChrootPackageVersion:
    def test_parses_repoquery_output(self):
        chroot_package_version.cache_clear()
        with patch("lib.toolchain.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "1.22.3\n"
            assert chroot_package_version("golang", "43") == "1.22.3"

    def test_repoquery_failure_returns_none(self):
        chroot_package_version.cache_clear()
        with patch("lib.toolchain.subprocess.run", side_effect=OSError("no dnf")):
            assert chroot_package_version("golang", "43") is None

    def test_empty_output_returns_none(self):
        chroot_package_version.cache_clear()
        with patch("lib.toolchain.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            assert chroot_package_version("golang", "43") is None


class TestGoToolchainSkew:
    def test_no_go_mod_is_none(self, tmp_path):
        assert go_toolchain_skew(tmp_path, "43") is None

    def test_chroot_too_old_reports_skew(self, tmp_path):
        (tmp_path / "go.mod").write_text("module foo\n\ntoolchain go1.23.0\n")
        with patch("lib.toolchain.chroot_package_version", return_value="1.22.0"):
            skew = go_toolchain_skew(tmp_path, "43")
        assert skew is not None
        assert "1.23.0" in skew and "1.22.0" in skew

    def test_chroot_new_enough_is_none(self, tmp_path):
        (tmp_path / "go.mod").write_text("module foo\n\ntoolchain go1.22.0\n")
        with patch("lib.toolchain.chroot_package_version", return_value="1.23.0"):
            assert go_toolchain_skew(tmp_path, "43") is None

    def test_unknown_chroot_version_is_none(self, tmp_path):
        (tmp_path / "go.mod").write_text("module foo\n\ntoolchain go1.23.0\n")
        with patch("lib.toolchain.chroot_package_version", return_value=None):
            assert go_toolchain_skew(tmp_path, "43") is None


class TestRustToolchainSkew:
    def test_no_cargo_toml_is_none(self, tmp_path):
        assert rust_toolchain_skew(tmp_path, "43") is None

    def test_chroot_too_old_reports_skew(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "foo"\nrust-version = "1.80"\n'
        )
        with patch("lib.toolchain.chroot_package_version", return_value="1.75.0"):
            skew = rust_toolchain_skew(tmp_path, "43")
        assert skew is not None
        assert "1.80" in skew and "1.75.0" in skew

    def test_chroot_new_enough_is_none(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "foo"\nrust-version = "1.75"\n'
        )
        with patch("lib.toolchain.chroot_package_version", return_value="1.80.0"):
            assert rust_toolchain_skew(tmp_path, "43") is None
