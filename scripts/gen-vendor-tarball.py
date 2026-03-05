#!/usr/bin/env python3
"""Generate a Go vendor tarball for a package.

Downloads the upstream source, runs `go mod vendor`, and produces
  <name>-<version>-vendor.tar.gz
in ~/rpmbuild/SOURCES/ (or --output-dir).

The resulting tarball unpacks as  vendor/  (no top-level directory wrapper),
so it can be extracted with `tar xf %{SOURCE1}` directly inside the build dir.

Usage:
    python3 scripts/gen-vendor-tarball.py spf13-cobra
    python3 scripts/gen-vendor-tarball.py spf13-cobra --output-dir /tmp/sources
    python3 scripts/gen-vendor-tarball.py spf13-cobra --keep-tmpdir
"""

import argparse
import sys
from pathlib import Path

from lib.vendor import VendorError, generate, vendor_tarball_path
from lib.yaml_utils import get_packages


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Go vendor tarball for a package defined in packages.yaml."
    )
    parser.add_argument("package", metavar="PACKAGE", help="package name, e.g. spf13-cobra")
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=str(Path.home() / "rpmbuild" / "SOURCES"),
        help="directory to write the vendor tarball (default: ~/rpmbuild/SOURCES)",
    )
    parser.add_argument(
        "--keep-tmpdir",
        action="store_true",
        help="do not remove the temporary work directory (useful for debugging)",
    )
    args = parser.parse_args()

    packages = get_packages()
    pkg_name = args.package
    if pkg_name not in packages:
        sys.exit(f"error: '{pkg_name}' not found in packages.yaml")

    pkg_meta = packages[pkg_name]
    version = str(pkg_meta.get("version", ""))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = vendor_tarball_path(pkg_name, version, output_dir)

    print(f"\n{'='*20} {pkg_name} {version} {'='*20}")
    print(f"  vendor tarball: {output_path}")

    try:
        generate(pkg_name, pkg_meta, output_path, keep_tmpdir=args.keep_tmpdir)
        print(f"\nwrote: {output_path}")
    except VendorError as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
