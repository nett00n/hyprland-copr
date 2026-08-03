"""Rust crate vendoring for COPR builds.

Generates vendor tarballs for Rust packages with pure crates.io dependencies
(no git sources). Works with cargo vendor + offline build.
"""

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
    """Generate vendor tarball from a downloaded, already-extracted source tree.

    Raises VendorError on failure.
    """
    # Check if cargo is available
    if shutil.which("cargo") is None:
        raise VendorError("'cargo' not found in PATH")

    _log = _log_fn(log_path)

    # Check cargo version
    try:
        check = subprocess.run(
            ["cargo", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if check.returncode != 0:
            raise VendorError(f"cargo check failed: {check.stderr.strip()}")
    except FileNotFoundError:
        raise VendorError("'cargo' not found in PATH")

    # Handle Rust subdirectory if specified
    rust_subdir = pkg_meta.get("build", {}).get("rust_subdir", "")
    if rust_subdir:
        src_dir = src_dir / rust_subdir

    if not (src_dir / "Cargo.toml").exists():
        raise VendorError(f"no Cargo.toml in extracted source at {src_dir}")

    vendor_dir = src_dir / "vendor"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)

    cargo_config_dir = src_dir / ".cargo"
    if cargo_config_dir.exists():
        shutil.rmtree(cargo_config_dir)

    _log("running: cargo vendor vendor/")
    result = subprocess.run(
        ["cargo", "vendor", str(vendor_dir)],
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
        raise VendorError(f"cargo vendor failed: {result.stderr.strip()}")

    if not vendor_dir.exists():
        raise VendorError("cargo vendor produced no vendor/ directory")

    cargo_config_dir.mkdir(exist_ok=True)
    cargo_config = cargo_config_dir / "config.toml"
    config_content = """[source.crates-io]
replace-with = 'vendored-sources'

[source.vendored-sources]
directory = 'vendor'

[net]
offline = true
"""
    cargo_config.write_text(config_content)
    _log("created .cargo/config.toml")

    # Create vendor tarball (contains only vendor/ and .cargo/config.toml)
    _log(f"packing vendor/ -> {output.name}")
    with tarfile.open(output, "w:gz") as tf:
        tf.add(vendor_dir, arcname="vendor")
        tf.add(cargo_config, arcname=".cargo/config.toml")

    _log("done")
