"""Go module vendoring for stage-vendor.py."""

import shutil
import subprocess
import tarfile
from pathlib import Path

from lib.vendor import VendorError, _log_fn


def generate(
    pkg_name: str,
    pkg_meta: dict,
    tmpdir: Path,
    src_dir: Path,
    output: Path,
    log_path: Path | None = None,
) -> None:
    """Generate vendor tarball for a Go package using go mod vendor.

    Raises VendorError on failure.
    """
    # Check if go is available
    try:
        result = subprocess.run(
            ["go", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise VendorError(f"go check failed: {result.stderr.strip()}")
    except FileNotFoundError:
        raise VendorError("'go' not found in PATH (or not executable)")

    _log = _log_fn(log_path)

    go_subdir = pkg_meta.get("build", {}).get("go_subdir", "")
    if go_subdir:
        src_dir = src_dir / go_subdir

    if not (src_dir / "go.mod").exists():
        raise VendorError(f"no go.mod in extracted source at {src_dir}")

    vendor_dir = src_dir / "vendor"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)

    _log("running: go mod vendor")
    result = subprocess.run(
        ["go", "mod", "vendor"],
        cwd=src_dir,
        capture_output=True,
        text=True,
    )
    if log_path:
        with open(log_path, "a") as fh:
            if result.stdout:
                fh.write(result.stdout)
            if result.stderr:
                fh.write(result.stderr)
            fh.write(f"[exit: {result.returncode}]\n\n")
    if result.returncode != 0:
        raise VendorError(f"go mod vendor failed: {result.stderr.strip()}")

    if not vendor_dir.exists():
        raise VendorError("go mod vendor produced no vendor/ directory")

    _log(f"packing vendor/ -> {output.name}")
    with tarfile.open(output, "w:gz") as tf:
        tf.add(vendor_dir, arcname="vendor")
