"""Rust crate vendoring for COPR builds.

Generates vendor tarballs for Rust packages with pure crates.io dependencies
(no git sources). Works with cargo vendor + offline build.
"""

import json
import shutil
import subprocess
import tarfile
from pathlib import Path

from lib.subprocess_utils import run_cmd
from lib.toolchain import rust_toolchain_skew
from lib.vendor import VendorError, _log_fn


def _find_git_source_crates(vendor_dir: Path) -> list[str]:
    """Return the names of vendored crates whose source isn't crates.io.

    `cargo vendor` writes a `.cargo-checksum.json` per crate; registry crates
    carry a `"package"` checksum, git/path crates carry `"package": null`
    since they were never published (docs/packaging.md TODO-0005) -- those
    can't be re-resolved offline in the mock chroot.
    """
    found = []
    for crate_dir in sorted(vendor_dir.iterdir()):
        if not crate_dir.is_dir():
            continue
        checksum_file = crate_dir / ".cargo-checksum.json"
        if not checksum_file.exists():
            continue
        try:
            data = json.loads(checksum_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("package") is None:
            found.append(crate_dir.name)
    return found


def generate(
    pkg_name: str,
    pkg_meta: dict,
    tmpdir: Path,
    src_dir: Path,
    output: Path,
    log_path: Path | None = None,
    fedora_version: str | None = None,
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

    if fedora_version:
        skew = rust_toolchain_skew(src_dir, fedora_version)
        if skew:
            raise VendorError(skew)

    # Bump specific crates past an upstream Cargo.lock pin that's broken
    # against the vendoring toolchain (e.g. a `time` version rustc's type
    # inference regressed against) -- semver-compatible only, no --precise,
    # so this stays self-healing as crates.io publishes further fixes.
    for spec in pkg_meta.get("build", {}).get("cargo_update", []):
        _log(f"running: cargo update -p {spec}")
        ok, _, stderr = run_cmd(
            ["cargo", "update", "-p", spec], log_path=log_path, cwd=src_dir
        )
        if not ok:
            raise VendorError(f"cargo update -p {spec} failed: {stderr.strip()}")

    vendor_dir = src_dir / "vendor"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)

    cargo_config_dir = src_dir / ".cargo"
    if cargo_config_dir.exists():
        shutil.rmtree(cargo_config_dir)

    _log("running: cargo vendor vendor/")
    ok, _, stderr = run_cmd(
        ["cargo", "vendor", str(vendor_dir)], log_path=log_path, cwd=src_dir
    )
    if not ok:
        raise VendorError(f"cargo vendor failed: {stderr.strip()}")

    if not vendor_dir.exists():
        raise VendorError("cargo vendor produced no vendor/ directory")

    git_crates = _find_git_source_crates(vendor_dir)
    if git_crates:
        raise VendorError(
            "git-source crate(s) unresolvable offline: "
            f"{', '.join(git_crates)} -- see docs/packaging.md 'Rust vendoring'"
        )

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
