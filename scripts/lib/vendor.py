"""Go vendor tarball helpers shared by stage-vendor.py and gen-vendor-tarball.py."""

import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


class VendorError(Exception):
    pass


def is_go_package(meta: dict) -> bool:
    """Return True if the package requires vendoring (has golang in build_requires)."""
    return "golang" in meta.get("build_requires", [])


def resolve_source_url(pkg_meta: dict, pkg_name: str) -> str:
    """Resolve the first source URL, expanding %{url} and %{version} macros."""
    sources = pkg_meta.get("sources", [])
    if not sources:
        raise VendorError(f"no sources defined for '{pkg_name}'")
    entry = sources[0]
    raw_url = entry if isinstance(entry, str) else entry.get("url", "")
    if not raw_url:
        raise VendorError(f"cannot determine source URL for '{pkg_name}'")
    url = pkg_meta.get("url", "")
    version = str(pkg_meta.get("version", ""))
    raw_url = raw_url.replace("%{url}", url).replace("%{version}", version).strip('"')
    return raw_url


def vendor_tarball_name(pkg_name: str, version: str) -> str:
    return f"{pkg_name}-{version}-vendor.tar.gz"


def vendor_tarball_path(pkg_name: str, version: str, sources_dir: Path) -> Path:
    return sources_dir / vendor_tarball_name(pkg_name, version)


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as resp:
        dest.write_bytes(resp.read())


def _extract(archive: Path, target_dir: Path) -> Path:
    with tarfile.open(archive) as tf:
        top_dirs = {m.name.split("/")[0] for m in tf.getmembers() if m.name}
        tf.extractall(target_dir, filter="data")
    if len(top_dirs) == 1:
        return target_dir / top_dirs.pop()
    return target_dir


def generate(
    pkg_name: str,
    pkg_meta: dict,
    output: Path,
    log_path: Path | None = None,
    keep_tmpdir: bool = False,
) -> None:
    """Download source, run go mod vendor, write vendor tarball to output.

    Raises VendorError on failure.
    """
    if shutil.which("go") is None:
        raise VendorError("'go' not found in PATH")

    source_url = resolve_source_url(pkg_meta, pkg_name)
    tmpdir = Path(tempfile.mkdtemp(prefix=f"govendor-{pkg_name}-"))

    def _log(msg: str) -> None:
        print(f"  {msg}", flush=True)
        if log_path:
            with open(log_path, "a") as fh:
                fh.write(msg + "\n")

    try:
        _log(f"downloading {source_url}")
        archive = tmpdir / "source.tar.gz"
        _download(source_url, archive)

        src_dir = _extract(archive, tmpdir)

        go_subdir = pkg_meta.get("go_subdir", "")
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

    finally:
        if not keep_tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            _log(f"tmpdir kept: {tmpdir}")
