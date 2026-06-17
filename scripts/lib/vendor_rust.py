"""Rust crate vendoring for COPR builds.

Generates vendor tarballs for Rust packages with pure crates.io dependencies
(no git sources). Works with cargo vendor + offline build.
"""

import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from lib.paths import SOURCES_DIR
from lib.vendor import VendorError, _download, _extract, _log_fn, resolve_source_url


def generate(
    pkg_name: str,
    pkg_meta: dict,
    output: Path,
    log_path: Path | None = None,
    keep_tmpdir: bool = False,
    submodule_path: Path | None = None,
) -> None:
    """Generate vendor tarball from local submodule or downloaded source.

    If submodule_path is provided and exists, uses that directly.
    Otherwise downloads source from URL in pkg_meta.
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

    # Determine source directory
    if submodule_path and submodule_path.exists():
        _log(f"using local submodule: {submodule_path}")
        src_dir = submodule_path
        tmpdir = None
    else:
        # Download source
        source_url = resolve_source_url(pkg_meta, pkg_name)
        tmpdir = Path(tempfile.mkdtemp(prefix=f"rustvendor-{pkg_name}-"))

        try:
            _log(f"downloading {source_url}")
            archive = tmpdir / "source.tar.gz"
            _download(source_url, archive)
            src_dir = _extract(archive, tmpdir)
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    try:
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

        if submodule_path and submodule_path.exists():
            root_arc_name = f"{pkg_name}-{pkg_meta.get('version')}"
            source_tarball = SOURCES_DIR / f"{root_arc_name}.tar.gz"

            if not source_tarball.exists():
                _log(f"creating source archive: {root_arc_name}.tar.gz")
                SOURCES_DIR.mkdir(parents=True, exist_ok=True)
                with tarfile.open(source_tarball, "w:gz") as tf:
                    # Add all source files except .git and __pycache__ and vendor
                    for item in sorted(src_dir.rglob("*")):
                        # Skip .git, __pycache__, vendor (already in vendor tarball), and .cargo (already in vendor tarball)
                        if any(
                            part in (".git", "__pycache__", "vendor", ".cargo")
                            for part in item.parts
                        ):
                            continue
                        if item.is_file():
                            arcname = f"{root_arc_name}/{item.relative_to(src_dir)}"
                            tf.add(item, arcname=arcname, recursive=False)

        _log("done")

    finally:
        # Only cleanup tmpdir if we created one (not for local submodules)
        if tmpdir is not None:
            if not keep_tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
            else:
                _log(f"tmpdir kept: {tmpdir}")
