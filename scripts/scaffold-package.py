#!/usr/bin/env python3
"""Detect build system/license/deps and scaffold a new packages.yaml entry.

Usage:
    python3 scripts/scaffold-package.py hyprpicker
"""

import argparse
import sys
from pathlib import Path

import yaml

from lib.detection import (
    detect_build_system,
    detect_license,
    extract_cmake_info,
    extract_version,
)
from lib.gitmodules import (
    fetch_tags,
    get_submodule_commit,
    parse_gitmodules,
    resolve_module,
)
from lib.paths import GITMODULES, PACKAGES_YAML, ROOT
from lib.version import latest_semver


def cmd_add(modules: list[dict], pkg_name: str) -> None:
    """Extract info from a submodule repo and append a scaffold entry to packages.yaml."""
    mod = resolve_module(modules, pkg_name)
    if mod is None:
        print(
            f"error: submodule '{pkg_name}' not found in .gitmodules", file=sys.stderr
        )
        print("available submodules:", file=sys.stderr)
        for m in modules:
            print(f"  {Path(m['path']).name}", file=sys.stderr)
        sys.exit(1)

    key = Path(mod["path"]).name
    url = mod["url"]
    repo = ROOT / mod["path"]

    if PACKAGES_YAML.exists():
        data = yaml.safe_load(PACKAGES_YAML.read_text()) or {}
        if key in data.get("packages", {}):
            print(f"error: '{key}' already exists in packages.yaml", file=sys.stderr)
            sys.exit(1)

    version = extract_version(repo)
    if version is None:
        print(f"fetching tags to determine version: {key} ...", file=sys.stderr)
        tags = fetch_tags(url)
        latest = latest_semver(tags)
    else:
        latest = version

    commit_lines: list[str] = []
    if latest:
        version = latest.lstrip("v") if isinstance(latest, str) else str(latest)
        source_url = '"%{url}/archive/refs/tags/v%{version}.tar.gz"'
    else:
        commit_info = get_submodule_commit(repo)
        if commit_info:
            full_hash, short_hash, date_str = commit_info
            version = f"0^{date_str}git{short_hash}"
            commit_lines = [
                "    commit:\n",
                f"      full: {full_hash}\n",
                f'      date: "{date_str}"\n',
            ]
            source_url = '"%{url}/archive/%{commit}.tar.gz"'
        else:
            version = "FIXME"
            source_url = '"%{url}/archive/refs/tags/v%{version}.tar.gz"'

    build_system = detect_build_system(repo) or "FIXME"
    license_id = detect_license(repo) or "FIXME"

    summary = "FIXME"
    pkg_deps: list[str] = []
    cmake = repo / "CMakeLists.txt"
    if cmake.exists():
        cmake_info = extract_cmake_info(cmake.read_text(errors="replace"))
        summary = cmake_info.get("summary", "FIXME")
        pkg_deps = cmake_info.get("pkg_deps", [])

    build_requires: list[str] = []
    if build_system == "cmake":
        build_requires += ["cmake", "ninja-build", "gcc-c++"]
    elif build_system == "meson":
        build_requires += ["meson", "ninja-build", "gcc-c++"]
    for dep in pkg_deps:
        build_requires.append(f"pkgconfig({dep})")

    lines = [
        f"\n  {key}:\n",
        f'    version: "{version}"\n',
        f'    release: "%autorelease"\n',  # noqa: F541
        f"    license: {license_id}\n",
        f"    summary: {summary}\n",
        f"    description: |\n",  # noqa: F541
        f"      FIXME\n",  # noqa: F541
        f"    url: {url}\n",
        *commit_lines,
        f"    sources:\n",  # noqa: F541
        f"      - url: {source_url}\n",
        f"    build_system: {build_system}\n"

    ]
    if build_requires:
        lines.append("    build_requires:\n")
        for dep in build_requires:
            lines.append(f"      - {dep}\n")
    else:
        lines.append("    build_requires: []  # FIXME\n")
    lines += [
        "    files:\n",
        '      - "%license LICENSE"\n',
        '      - "%doc README.md"\n',
        "      - # FIXME: add installed files\n",
    ]

    block = "".join(lines)

    if PACKAGES_YAML.exists():
        with PACKAGES_YAML.open("a") as f:
            f.write(block)
    else:
        PACKAGES_YAML.write_text(f"packages:\n{block}")

    print(f"appended '{key}' to {PACKAGES_YAML}", file=sys.stderr)
    print(block)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new packages.yaml entry from a submodule repo."
    )
    parser.add_argument(
        "package",
        metavar="PACKAGE",
        help="submodule name, e.g. hyprpicker",
    )
    args = parser.parse_args()

    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)
    cmd_add(modules, args.package)


if __name__ == "__main__":
    main()
