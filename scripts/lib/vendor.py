"""Vendor tarball helpers for multiple languages (Go, Rust)."""

import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


class VendorError(Exception):
    pass


def _log_fn(log_path: Path | None):
    """Return a logging function that writes to stdout and optionally to a file."""

    def _log(msg: str) -> None:
        print(f"  {msg}", flush=True)
        if log_path:
            with open(log_path, "a") as fh:
                fh.write(msg + "\n")

    return _log


def is_go_package(meta: dict) -> bool:
    """Return True if the package requires vendoring (has golang in build_requires)."""
    return "golang" in (meta.get("build_requires") or [])


def is_rust_package(meta: dict) -> bool:
    """Return True if the package requires Rust vendoring (has cargo in build_requires)."""
    return "cargo" in (meta.get("build_requires") or [])


def resolve_source_url(pkg_meta: dict, pkg_name: str) -> str:
    """Resolve the first source URL, expanding %{url}, %{name}, and %{version} macros.

    Strips .git from URL since GitHub archive endpoints do not accept it.
    """
    from lib.spec_utils import process_archive_urls

    archives = pkg_meta.get("source", {}).get("archives", [])
    if not archives:
        raise VendorError(f"no sources defined for '{pkg_name}'")
    raw_url = archives[0]
    if not raw_url:
        raise VendorError(f"cannot determine source URL for '{pkg_name}'")

    # Use shared archive processing to ensure .git is stripped
    processed = process_archive_urls(
        [raw_url],
        pkg_meta.get("url", ""),
        pkg_name,
        pkg_meta.get("source", {}).get("commit")
        if isinstance(pkg_meta.get("source", {}).get("commit"), dict)
        else None,
        str(pkg_meta.get("version", "")),
    )
    raw_url = str(processed[0]).strip('"')
    return raw_url


def vendor_tarball_name(pkg_name: str, version: str) -> str:
    return f"{pkg_name}-{version}-vendor.tar.gz"


def vendor_tarball_path(pkg_name: str, version: str, sources_dir: Path) -> Path:
    return sources_dir / vendor_tarball_name(pkg_name, version)


def _download(url: str, dest: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        raise VendorError(f"failed to download {url}: {e}") from e
    except OSError as e:
        raise VendorError(f"failed to download {url}: {e}") from e


def _extract(archive: Path, target_dir: Path) -> Path:
    with tarfile.open(archive) as tf:
        top_dirs = {m.name.split("/")[0] for m in tf.getmembers() if m.name}
        # filter="data" prevents path traversal attacks but requires Python 3.12+
        try:
            tf.extractall(target_dir, filter="data")  # type: ignore
        except TypeError:
            # Fall back for Python < 3.12: manual member validation
            for member in tf.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    raise VendorError(f"Unsafe tarball member: {member.name}")
            tf.extractall(target_dir)
    if len(top_dirs) == 1:
        return target_dir / top_dirs.pop()
    return target_dir


def generate(
    pkg_name: str,
    pkg_meta: dict,
    output: Path,
    log_path: Path | None = None,
    keep_tmpdir: bool = False,
    submodule_path: Path | None = None,
) -> None:
    """Download source (or use local submodule), run vendor tool, write vendor tarball.

    Dispatches to language-specific vendor implementation.
    Raises VendorError on failure.
    """
    if is_rust_package(pkg_meta):
        from lib.vendor_rust import generate as generate_rust

        return generate_rust(
            pkg_name, pkg_meta, output, log_path, keep_tmpdir, submodule_path
        )

    if is_go_package(pkg_meta):
        from lib.vendor_golang import generate as generate_go

        source_url = resolve_source_url(pkg_meta, pkg_name)
        tmpdir = Path(tempfile.mkdtemp(prefix=f"govendor-{pkg_name}-"))
        try:
            _log = _log_fn(log_path)
            _log(f"downloading {source_url}")
            archive = tmpdir / "source.tar.gz"
            _download(source_url, archive)
            src_dir = _extract(archive, tmpdir)
            return generate_go(pkg_name, pkg_meta, tmpdir, src_dir, output, log_path)
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise
        finally:
            if keep_tmpdir:
                _log = _log_fn(log_path)
                _log(f"tmpdir kept: {tmpdir}")
            elif tmpdir.exists():
                shutil.rmtree(tmpdir, ignore_errors=True)

    raise VendorError(
        f"'{pkg_name}' is not a Go or Rust package (no 'golang' or 'cargo' in build_requires)"
    )
