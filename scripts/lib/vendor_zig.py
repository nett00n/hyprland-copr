"""Zig package vendoring for stage-vendor.py (#COPR-0027)."""

import shutil
import subprocess
import tarfile
from pathlib import Path

from lib.subprocess_utils import run_cmd
from lib.toolchain import zig_toolchain_skew
from lib.vendor import VendorError, log_fn


# #COPR-0027
def generate(
    pkg_name: str,
    pkg_meta: dict,
    tmpdir: Path,
    src_dir: Path,
    output: Path,
    log_path: Path | None = None,
    fedora_version: str | None = None,
) -> None:
    """Generate the vendor tarball for a Zig package: `zig build --fetch`
    unpacks every build.zig.zon dependency into `zig-pkg/<hash>/` (the Zig 0.16
    layout), which is packed as-is. The chroot build then runs offline with
    `--system zig-pkg` (zig-rpm-macros' %zig_build does this).

    Raises VendorError on failure.
    """
    try:
        result = subprocess.run(
            ["zig", "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            raise VendorError(f"zig check failed: {result.stderr.strip()}")
    except FileNotFoundError as e:
        raise VendorError("'zig' not found in PATH (or not executable)") from e
    except subprocess.TimeoutExpired as e:
        raise VendorError("'zig version' timed out") from e

    _log = log_fn(log_path)

    if not (src_dir / "build.zig.zon").exists():
        raise VendorError(f"no build.zig.zon in extracted source at {src_dir}")

    if fedora_version:
        skew = zig_toolchain_skew(src_dir, fedora_version)
        if skew:
            raise VendorError(skew)

    pkg_dir = src_dir / "zig-pkg"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)

    _log("running: zig build --fetch")
    ok, _, stderr = run_cmd(
        ["zig", "build", "--fetch", "--global-cache-dir", str(tmpdir / "zig-cache")],
        log_path=log_path,
        cwd=src_dir,
    )
    if not ok:
        raise VendorError(f"zig build --fetch failed: {stderr.strip()}")

    # A project without dependencies fetches nothing; the tarball (Source1) must
    # still exist and extract cleanly, so pack an empty zig-pkg/.
    pkg_dir.mkdir(exist_ok=True)

    _log(f"packing zig-pkg/ -> {output.name}")
    with tarfile.open(output, "w:gz") as tf:
        tf.add(pkg_dir, arcname="zig-pkg")
