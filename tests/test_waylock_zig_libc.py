"""The waylock spec links zig against the chroot's real glibc (#COPR-0027)."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.yaml_utils import get_packages  # noqa: E402

stage_spec = importlib.import_module("scripts.stage-spec")


def _spec() -> str:
    packages = get_packages()
    return stage_spec.generate_spec("waylock", packages["waylock"], packages, "44")


def _section(spec: str, start: str, end: str) -> str:
    return spec.split(start, 1)[1].split(end, 1)[0]


class TestWaylockZigLibc:
    def test_build_writes_libc_file_before_zig_build(self):
        build = _section(_spec(), "%build", "%install")
        assert "zig-libc.txt" in build
        assert build.index("> zig-libc.txt") < build.index("%zig_build")

    def test_libc_file_uses_chroot_paths(self):
        build = _section(_spec(), "%build", "%install")
        assert "include_dir=%{_includedir}" in build
        assert "crt_dir=%{_libdir}" in build

    def test_build_and_install_pass_libc_flag(self):
        spec = _spec()
        build = _section(spec, "%build", "%install")
        install = _section(spec, "%install", "%files")
        assert "%zig_build -Dpie -Dllvm=true --libc zig-libc.txt" in build
        assert "%zig_install -Dpie -Dllvm=true --libc zig-libc.txt" in install
