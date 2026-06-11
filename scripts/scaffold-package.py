#!/usr/bin/env python3
"""Detect build system/license/deps and scaffold a new packages.yaml entry.

Usage:
    python3 scripts/scaffold-package.py hyprpicker
"""

import argparse
import sys
from pathlib import Path

import yaml
from ruamel.yaml import YAML

from lib.detection import (
    detect_build_system,
    detect_license,
    extract_cmake_info,
    extract_meson_info,
    extract_version,
)
from lib.tarball import detect_tarball_source_name
from lib.gitmodules import (
    fetch_tags,
    get_submodule_commit_with_base,
    parse_gitmodules,
    resolve_module,
)
from lib.paths import GITMODULES, PACKAGES_YAML, ROOT
from lib.version import latest_semver
from lib.yaml_config import DEFAULT as YAML_CONFIG


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
    url = mod["url"].removesuffix(".git")
    repo = ROOT / mod["path"]

    if PACKAGES_YAML.exists():
        existing = yaml.safe_load(PACKAGES_YAML.read_text()) or {}
        if key in existing:
            print(f"error: '{key}' already exists in packages.yaml", file=sys.stderr)
            sys.exit(1)
    else:
        existing = {}

    version = extract_version(repo)
    if version is None:
        print(f"fetching tags to determine version: {key} ...", file=sys.stderr)
        tags = fetch_tags(url)
        latest = latest_semver(tags)
    else:
        latest = version

    commit = None
    if latest:
        version = latest.lstrip("v") if isinstance(latest, str) else str(latest)
        source_url = (
            "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
        )
    else:
        commit_info = get_submodule_commit_with_base(repo)
        if commit_info:
            full_hash, short_hash, date_str, base_semver = commit_info
            prefix = base_semver if base_semver else "0"
            version = f"{prefix}^{date_str}git{short_hash}"
            commit = {"full": full_hash, "date": date_str}
            source_url = "%{url}/archive/%{commit}.tar.gz"
        else:
            version = "FIXME"
            source_url = (
                "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
            )

    build_system = detect_build_system(repo) or "FIXME"
    license_id = detect_license(repo) or "FIXME"

    summary = "FIXME"
    pkg_deps: list[str] = []
    cmake = repo / "CMakeLists.txt"
    if cmake.exists():
        cmake_info = extract_cmake_info(cmake.read_text(errors="replace"))
        summary = cmake_info.get("summary", "FIXME")
        pkg_deps = cmake_info.get("pkg_deps", [])
    meson_build = repo / "meson.build"
    if meson_build.exists() and build_system == "meson":
        meson_info = extract_meson_info(meson_build.read_text(errors="replace"))
        if summary == "FIXME":
            summary = meson_info.get("summary", "FIXME")
        pkg_deps = meson_info.get("pkg_deps", [])

    build_requires: list[str] = []
    if build_system == "cmake":
        build_requires += ["cmake", "ninja-build", "gcc-c++"]
    elif build_system == "meson":
        build_requires += ["meson", "ninja-build", "gcc-c++"]
    elif build_system == "cargo":
        build_requires += ["cargo", "rustc"]
    for dep in pkg_deps:
        build_requires.append(f"pkgconfig({dep})")

    pkg_by_lower = {k.lower(): k for k in existing}
    depends_on: list[str] = []
    for req in build_requires:
        base: str | None = None
        if req.endswith("-devel"):
            base = req[:-6].lower()
        elif req.startswith("pkgconfig(") and req.endswith(")"):
            base = req[10:-1].lower()
        if base and base in pkg_by_lower and pkg_by_lower[base] != key:
            resolved = pkg_by_lower[base]
            if resolved not in depends_on:
                depends_on.append(resolved)

    if version != "FIXME":
        if commit:
            tar_urls = [f"{url}/archive/{commit['full']}.tar.gz"]
            version_or_commit = commit["full"]
        else:
            tar_urls = [
                f"{url}/archive/refs/tags/v{version}.tar.gz",
                f"{url}/archive/refs/tags/{version}.tar.gz",
            ]
            version_or_commit = version
        print("probing tarball for source_name ...", file=sys.stderr)
        source_name = (
            detect_tarball_source_name(tar_urls, key.lower(), version_or_commit) or ""
        )
    else:
        source_name = ""

    entry = {
        "version": version,
        "release": "%autorelease",
        "license": license_id,
        "summary": summary,
        "description": "FIXME",
        "url": url,
        "depends_on": depends_on if depends_on else [],
        "build_requires": build_requires if build_requires else [],
        "requires": [],
        "files": [
            "%license LICENSE",
            "%doc README.md",
            *([f"%{{_bindir}}/{key}"] if build_system == "golang" else []),
        ],
        "devel": {"files": []},
        "source": {
            "archives": [source_url],
        },
        "build": {
            "system": build_system,
            "prep": [],
            "commands": [],
            "install": [],
            "no_lto": False,
        },
        "rpm": {
            "no_debug_package": False,
        },
    }

    if source_name:
        entry["source"]["name"] = source_name

    if commit:
        entry["source"]["commit"] = commit

    if PACKAGES_YAML.exists():
        yml = YAML()
        yml.default_flow_style = False
        yml.allow_unicode = True
        yml.indent(mapping=2, sequence=2, offset=0)
        with PACKAGES_YAML.open() as f:
            data = yml.load(f)
        if data is None:
            data = {}
        data[key] = entry
    else:
        data = {key: entry}

    PACKAGES_YAML.write_text(YAML_CONFIG.dump(data))

    print(f"appended '{key}' to {PACKAGES_YAML}", file=sys.stderr)
    print(YAML_CONFIG.dump({key: entry}))


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
