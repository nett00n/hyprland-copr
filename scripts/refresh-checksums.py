#!/usr/bin/env python3
"""Record sha256 checksums for upstream source tarballs into sources.lock.yaml.

Downloads each package's remote sources (see lib.source_lock.remote_sources)
into ~/rpmbuild/SOURCES if not already present, hashes them, and writes the
result to the committed sources.lock.yaml. This is the only script that
writes that file -- stage-srpm.py and the vendor download path only ever
read it, and fail closed on anything unrecorded (see docs/CHANGELOG.md BUG-0025).

An existing entry whose filename is unchanged but whose hash differs (a
retag, a tampered mirror, ...) is refused unless FORCE_CHECKSUM=1 is set --
that is exactly the case this bug exists to catch, so silently overwriting
it would defeat the point.

Not tied to a build target: checksums are the same across every Fedora
version/chroot, so this runs once regardless of FEDORA_VERSION/MOCK_CHROOT.

Environment variables:
  PACKAGE         Record only this package (optional, comma-separated)
  SKIP_PACKAGES   Skip these packages (optional, comma-separated)
  FORCE_CHECKSUM  Overwrite a conflicting recorded hash (true/1, default: false)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR

Usage:
  refresh-checksums.py           record/update sources.lock.yaml
  refresh-checksums.py --check   verify only; no download, no write
                                  (same as `make check-checksums`)
"""

import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from lib.config import setup_logging
from lib.paths import SOURCES_DIR
from lib.source_lock import record, remote_sources, verify
from lib.yaml_utils import filter_packages, get_packages, skip_packages


def _download(url: str, dest: Path, timeout: int = 60) -> str | None:
    """Download `url` to `dest`. Returns None on success, an error string on failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
    except (urllib.error.URLError, OSError) as e:
        return str(e)
    return None


def _select_packages() -> dict:
    all_packages = get_packages()
    packages = filter_packages(all_packages, os.environ.get("PACKAGE", ""))
    return skip_packages(packages, os.environ.get("SKIP_PACKAGES", ""))


def check_only(packages: dict) -> bool:
    """Verify-only pass: report problems, write nothing. Returns True if all clean."""
    ok = True
    for pkg, meta in packages.items():
        if not remote_sources(pkg, meta):
            continue
        problems = verify(pkg, meta, SOURCES_DIR)
        if problems:
            ok = False
            print(f"  [FAIL] {pkg}")
            for p in problems:
                print(f"    {p}")
        else:
            print(f"  [OK]   {pkg}")
    return ok


def refresh(packages: dict, force: bool) -> bool:
    """Download any missing remote sources and record their hashes. Returns True on success."""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    ok = True
    for pkg, meta in packages.items():
        sources = remote_sources(pkg, meta)
        if not sources:
            continue
        for filename, url in sources:
            dest = SOURCES_DIR / filename
            if dest.exists():
                continue
            print(f"  [GET]  {pkg}: {filename}")
            err = _download(url, dest)
            if err is not None:
                print(f"  [FAIL] {pkg}: {filename}: {err}")
                ok = False

        recorded, skipped = record(pkg, meta, SOURCES_DIR, force=force)
        for filename, digest in recorded.items():
            print(f"  [OK]   {pkg}: {filename} sha256={digest}")
        for skip in skipped:
            print(f"  [WARN] {pkg}: {skip.filename}: {skip.message}")
            if skip.conflict:
                ok = False
    return ok


def main() -> None:
    check = "--check" in sys.argv[1:]
    force = os.environ.get("FORCE_CHECKSUM", "").lower() in ("1", "true")
    packages = _select_packages()

    print("\n=== check-checksums ===" if check else "\n=== refresh-checksums ===")
    ok = check_only(packages) if check else refresh(packages, force)

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
