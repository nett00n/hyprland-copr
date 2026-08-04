"""Content-addressed vendor tarball cache: .cache/vendor/<pkg>/<input-hash>/.

Distro/arch-independent by construction: unlike SOURCES_DIR (one podman volume
per FEDORA_VERSION), this store lives on the repo's own /work mount, so one
entry serves every target and `make full-cycle-matrix` builds a given vendor
tree once instead of once per Fedora version (docs/todo.md TODO-0006).

Keyed by lib.cache.compute_input_hashes -- the same mechanism every other
stage's cache uses -- so editing go_subdir/rust_subdir, the source URL, or a
patch invalidates the store exactly like it invalidates a normal stage cache,
instead of "does a file happen to exist" (docs/bugs.md BUG-0023).

Ownership/GC piggybacks on the existing `artifacts` table: stage-vendor.py
records store hits/writes under realm="vendor-store" with a sentinel target,
so `db-artifacts.py --prune` reclaims superseded entries the same way it
reclaims stale SRPMs/RPMs.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from lib import paths
from lib.cache import compute_input_hashes, hashes_match
from lib.vendor import is_go_package, is_rust_package

TARBALL_NAME = "vendor.tar.gz"
META_NAME = "meta.json"


def _digest(hashes: dict) -> str:
    return hashlib.sha256(
        json.dumps(hashes, sort_keys=True, default=str).encode()
    ).hexdigest()


def _entry_dir(pkg: str, hashes: dict) -> Path:
    return paths.VENDOR_STORE_DIR / pkg / _digest(hashes)


_TOOL_VERSION_CMD = {"rust": ["cargo", "--version"], "go": ["go", "version"]}


def _tool_version(language: str) -> str:
    """Best-effort tool version string recorded in meta.json.

    Informational only -- not part of the cache key. Reserved for the
    toolchain-skew check deferred to Phase 3 (docs/todo.md TODO-0007).
    """
    cmd = _TOOL_VERSION_CMD.get(language)
    if cmd is None:
        return ""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _language(meta: dict) -> str:
    if is_rust_package(meta):
        return "rust"
    if is_go_package(meta):
        return "go"
    return "unknown"


def find(pkg: str, meta: dict, all_packages: dict) -> Path | None:
    """Return the store's vendor tarball if a live entry matches pkg's current
    inputs, else None.

    A miss (no entry, or an entry whose tarball/meta.json was reclaimed by
    `db-artifacts.py --prune`) is an ordinary cache miss, not an error --
    callers fall back to generating the tarball and calling `store()`.
    """
    hashes = compute_input_hashes(pkg, meta, all_packages)
    entry_dir = _entry_dir(pkg, hashes)
    tarball = entry_dir / TARBALL_NAME
    meta_path = entry_dir / META_NAME
    if not (tarball.exists() and meta_path.exists()):
        return None
    try:
        stored = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not hashes_match({"hashes": stored.get("hashes")}, hashes):
        return None
    return tarball


def store(pkg: str, meta: dict, all_packages: dict, built_tarball: Path) -> Path:
    """Copy a freshly generated vendor tarball into the content-addressed
    store, alongside a meta.json recording what produced it.

    Returns the store's own tarball path (the caller keeps its own copy in
    the per-target SOURCES_DIR).
    """
    hashes = compute_input_hashes(pkg, meta, all_packages)
    entry_dir = _entry_dir(pkg, hashes)
    entry_dir.mkdir(parents=True, exist_ok=True)
    tarball = entry_dir / TARBALL_NAME
    shutil.copyfile(built_tarball, tarball)
    language = _language(meta)
    (entry_dir / META_NAME).write_text(
        json.dumps(
            {
                "package": pkg,
                "version": str(meta.get("version", "")),
                "language": language,
                "hashes": hashes,
                "tool_version": _tool_version(language),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return tarball
