"""Tests for vendor_zig module (#COPR-0027)."""

import subprocess
import sys
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.vendor_zig import VendorError, generate

ZON = '.{ .name = .foo, .version = "1.0.0", .paths = .{""} }\n'


def _ok(stdout="0.16.0", stderr=""):
    return MagicMock(returncode=0, stdout=stdout, stderr=stderr)


def _fake_fetch(pkgs=("wayland-0.6.0-abc",)):
    """A run_cmd stand-in that mimics `zig build --fetch` filling zig-pkg/."""

    def run(cmd, log_path=None, cwd=None, **_):
        for pkg in pkgs:
            (Path(cwd) / "zig-pkg" / pkg).mkdir(parents=True, exist_ok=True)
            (Path(cwd) / "zig-pkg" / pkg / "build.zig").write_text("")
        return True, "", ""

    return run


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "build.zig.zon").write_text(ZON)
    return d


class TestGenerate:
    @patch("lib.vendor_zig.subprocess.run", side_effect=FileNotFoundError())
    def test_zig_not_in_path(self, _run, tmp_path, src):
        with pytest.raises(VendorError, match="'zig' not found"):
            generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")

    @patch("lib.vendor_zig.subprocess.run")
    def test_zig_version_fails(self, run, tmp_path, src):
        run.return_value = MagicMock(returncode=1, stdout="", stderr="broken")
        with pytest.raises(VendorError, match="zig check failed"):
            generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    def test_no_build_zig_zon(self, _run, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(VendorError, match="build.zig.zon"):
            generate("pkg", {}, tmp_path, empty, tmp_path / "out.tar.gz")

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd", return_value=(False, "", "no network"))
    def test_fetch_failure(self, _cmd, _run, tmp_path, src):
        with pytest.raises(VendorError, match="zig build --fetch failed: no network"):
            generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    def test_fetch_command_args(self, cmd, _run, tmp_path, src):
        cmd.side_effect = _fake_fetch()
        generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")

        args = cmd.call_args.args[0]
        assert args[:3] == ["zig", "build", "--fetch"]
        assert args[args.index("--global-cache-dir") + 1] == str(tmp_path / "zig-cache")
        assert cmd.call_args.kwargs["cwd"] == src

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    def test_tarball_contains_zig_pkg(self, cmd, _run, tmp_path, src):
        cmd.side_effect = _fake_fetch(("wayland-0.6.0-abc", "xkbcommon-0.3.0-def"))
        out = tmp_path / "out.tar.gz"
        generate("pkg", {}, tmp_path, src, out)

        with tarfile.open(out) as tf:
            names = tf.getnames()
        assert "zig-pkg" in names
        assert "zig-pkg/wayland-0.6.0-abc/build.zig" in names
        assert "zig-pkg/xkbcommon-0.3.0-def/build.zig" in names

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    def test_no_dependencies_gives_empty_zig_pkg(self, cmd, _run, tmp_path, src):
        cmd.return_value = (True, "", "")
        out = tmp_path / "out.tar.gz"
        generate("pkg", {}, tmp_path, src, out)

        with tarfile.open(out) as tf:
            assert tf.getnames() == ["zig-pkg"]

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    def test_existing_zig_pkg_is_removed_first(self, cmd, _run, tmp_path, src):
        stale = src / "zig-pkg" / "stale-0.0.1-zzz"
        stale.mkdir(parents=True)
        cmd.side_effect = _fake_fetch()
        out = tmp_path / "out.tar.gz"
        generate("pkg", {}, tmp_path, src, out)

        with tarfile.open(out) as tf:
            assert not any("stale" in n for n in tf.getnames())

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    @patch("lib.vendor_zig.zig_toolchain_skew", return_value="needs zig 0.17")
    def test_skew_blocks_before_fetch(self, _skew, cmd, _run, tmp_path, src):
        with pytest.raises(VendorError, match="needs zig 0.17"):
            generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz", fedora_version="44")
        cmd.assert_not_called()

    @patch("lib.vendor_zig.subprocess.run", return_value=_ok())
    @patch("lib.vendor_zig.run_cmd")
    @patch("lib.vendor_zig.zig_toolchain_skew")
    def test_skew_not_checked_without_fedora_version(self, skew, cmd, _run, tmp_path, src):
        cmd.side_effect = _fake_fetch()
        generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")
        skew.assert_not_called()


class TestTimeout:
    @patch(
        "lib.vendor_zig.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="zig version", timeout=10),
    )
    def test_zig_version_timeout_is_a_vendor_error(self, _run, tmp_path, src):
        with pytest.raises(VendorError, match="timed out"):
            generate("pkg", {}, tmp_path, src, tmp_path / "out.tar.gz")
