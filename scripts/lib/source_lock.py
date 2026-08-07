"""Checksum pinning for remote upstream sources (BUG-0025).

`spectool -g -R` (stage-srpm.py) and the vendor download path (lib.vendor) both
pull a remote tarball and hand it straight to `rpmbuild -bs` / `cargo vendor`
with nothing checking what actually arrived -- a retagged upstream release, a
tampered mirror, or a truncated download becomes a published RPM with no
signal. This module is the single source of truth for "which remote files
does this package's build depend on" (`remote_sources`), plus the two halves
that use it:

- `record()` -- explicit, reviewed step (`make refresh-checksums`) that
  downloads a file once and pins its sha256 into the committed
  `sources.lock.yaml`.
- `verify()` -- read-only check run on every build (stage-srpm.py, the vendor
  download path) that a file already on disk matches its pinned hash.

Trust model is TOFU (trust-on-first-use): the lock proves the bytes have not
changed since the hash was first recorded and reviewed in a diff, not that
upstream was honest at record time. Signature verification is out of scope
here -- see docs/todo.md.
"""

import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from lib import paths
from lib.spec_utils import process_archive_urls
from lib.yaml_config import DEFAULT as DEFAULT_YAML_CONFIG

_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return the hex sha256 digest of `path`, reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_sources(pkg_name: str, meta: dict) -> list[tuple[str, str]]:
    """Return [(local_filename, url), ...] for every remote file this package's
    build downloads: `source.archives` entries plus `source.bundled_deps[*].url`.

    Local-only entries (vendor tarballs produced by stage-vendor, bare
    filenames with no scheme) are excluded -- they're not something a network
    download can tamper with. The local filename is taken from the URL
    fragment (`...#/name.tar.gz`, the same convention spectool uses to name
    the downloaded file) when present, else the URL's basename.
    """
    source = meta.get("source", {}) or {}
    archives = process_archive_urls(
        source.get("archives", []),
        meta.get("url", ""),
        pkg_name,
        source.get("commit") if isinstance(source.get("commit"), dict) else None,
        str(meta.get("version", "")),
    )

    urls: list[str] = []
    for a in archives:
        if isinstance(a, str) and a:
            urls.append(a)
    for dep in source.get("bundled_deps", []) or []:
        url = (dep or {}).get("url")
        if url:
            urls.append(url)

    result: list[tuple[str, str]] = []
    for url in urls:
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        base, _, fragment = url.partition("#")
        if fragment.startswith("/"):
            filename = fragment[1:]
        else:
            filename = Path(urlsplit(base).path).name
        if filename:
            result.append((filename, url))
    return result


def load_lock() -> dict:
    """Return the parsed sources.lock.yaml, or {} if it doesn't exist yet.

    Reads `paths.SOURCES_LOCK` at call time (not at import time) so tests can
    monkeypatch it per-test, same reasoning as lib.build_db.connect().
    """
    if not paths.SOURCES_LOCK.exists():
        return {}
    return yaml.safe_load(paths.SOURCES_LOCK.read_text()) or {}


def save_lock(lock: dict) -> None:
    """Write `lock` back to sources.lock.yaml."""
    paths.SOURCES_LOCK.write_text(DEFAULT_YAML_CONFIG.dump(lock))


def verify(pkg_name: str, meta: dict, sources_dir: Path) -> list[str]:
    """Check every remote source file for `pkg_name` against the committed lock.

    Returns a list of human-readable problems; empty means every remote file
    is present in `sources_dir` and matches its pinned sha256. Does not read
    the network -- it only checks files already downloaded (e.g. by
    `spectool -g`), so a stale/corrupted SOURCES cache is caught the same way
    a tampered download would be.
    """
    lock = load_lock()
    pkg_lock = lock.get(pkg_name, {})
    problems: list[str] = []

    for filename, _url in remote_sources(pkg_name, meta):
        entry = pkg_lock.get(filename)
        if entry is None:
            problems.append(
                f"{filename}: no entry in sources.lock.yaml -- "
                f"run: make refresh-checksums PACKAGE={pkg_name}"
            )
            continue
        path = sources_dir / filename
        if not path.exists():
            problems.append(f"{filename}: missing from {sources_dir}")
            continue
        actual = sha256_file(path)
        expected = entry.get("sha256")
        if actual != expected:
            problems.append(
                f"{filename}: sha256 mismatch (expected {expected}, got {actual})"
            )
    return problems


def missing_entries(packages: dict) -> list[str]:
    """Return names of packages that have a remote source with no entry at all in
    sources.lock.yaml -- the case stage-srpm.py fails closed on (BUG-0025).

    Distinct from a hash mismatch or an undownloaded file (both require the file
    on disk to detect and are a build-time concern, not a preflight one): this is
    the "nobody has ever run refresh-checksums for this package" case, which a
    freshly scaffolded/added package hits every time until someone remembers to.
    """
    lock = load_lock()
    missing: list[str] = []
    for pkg, meta in packages.items():
        pkg_lock = lock.get(pkg, {})
        if any(filename not in pkg_lock for filename, _url in remote_sources(pkg, meta)):
            missing.append(pkg)
    return missing


class Skip:
    """One file record() declined to (re)write. `conflict=True` means the
    recorded hash differs from the downloaded file's hash and force wasn't
    set -- the retag/tamper case this bug exists to catch, distinct from
    merely "not downloaded yet".
    """

    def __init__(self, filename: str, message: str, conflict: bool = False):
        self.filename = filename
        self.message = message
        self.conflict = conflict

    def __repr__(self) -> str:
        return f"Skip({self.filename!r}, conflict={self.conflict})"


def record(
    pkg_name: str, meta: dict, sources_dir: Path, force: bool = False
) -> tuple[dict[str, str], list[Skip]]:
    """Hash every remote source file for `pkg_name` present in `sources_dir` and
    write/update its entry in sources.lock.yaml.

    An existing entry whose filename is unchanged but whose hash differs is
    the retag/tamper case this bug is about, so it is refused unless
    `force=True` (make refresh-checksums FORCE_CHECKSUM=1).

    Returns (recorded, skipped): `recorded` maps filename -> sha256 for
    entries written this call; `skipped` lists the files that were not
    recorded, each flagged with whether it was a hash conflict (see `Skip`).
    """
    from datetime import date

    lock = load_lock()
    pkg_lock = lock.setdefault(pkg_name, {})
    recorded: dict[str, str] = {}
    skipped: list[Skip] = []

    for filename, url in remote_sources(pkg_name, meta):
        path = sources_dir / filename
        if not path.exists():
            skipped.append(Skip(filename, f"not present in {sources_dir}, skipped"))
            continue
        digest = sha256_file(path)
        existing = pkg_lock.get(filename)
        if existing and existing.get("sha256") != digest and not force:
            skipped.append(
                Skip(
                    filename,
                    f"recorded sha256 differs from downloaded file "
                    f"(expected {existing.get('sha256')}, got {digest}) -- refusing to "
                    "overwrite; pass FORCE_CHECKSUM=1 only after verifying the change "
                    "is legitimate (e.g. upstream retagged the release)",
                    conflict=True,
                )
            )
            continue
        pkg_lock[filename] = {
            "url": url,
            "sha256": digest,
            "size": path.stat().st_size,
            "recorded": date.today().isoformat(),
        }
        recorded[filename] = digest

    if recorded:
        save_lock(lock)
    return recorded, skipped
