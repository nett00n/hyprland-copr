#!/usr/bin/env python3
"""List latest semver tag for each submodule and update versions in packages.yaml."""

import argparse
import configparser
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Strict semver: v?MAJOR.MINOR.PATCH with no extra suffixes
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
# Package header in packages.yaml: 2-space indent, no leading dash
PKG_HEADER_RE = re.compile(r"^  (\w[\w\-]+):\s*(?:#.*)?$")
# Version line in packages.yaml: 4-space indent
VERSION_LINE_RE = re.compile(r'^    version: "([^"]+)"')
# pkg_check_modules() call (may span multiple lines)
PKG_CHECK_RE = re.compile(r"pkg_check_modules\s*\(([^)]+)\)", re.DOTALL)
# CMake keywords that appear inside pkg_check_modules() but are not package names
CMAKE_KEYWORDS = {
    "REQUIRED",
    "IMPORTED_TARGET",
    "QUIET",
    "NO_MODULE",
    "EXACT",
    "CONFIG",
    "MODULE",
    "STATIC",
    "GLOBAL",
}

LICENSE_MAP = [
    ("BSD 3-Clause", "BSD-3-Clause"),
    ("BSD 2-Clause", "BSD-2-Clause"),
    ("MIT License", "MIT"),
    ("MIT", "MIT"),
    ("Apache License", "Apache-2.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0-or-later"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL-3.0-or-later"),
    ("ISC License", "ISC"),
    ("Mozilla Public License", "MPL-2.0"),
]

ROOT = Path(__file__).resolve().parent.parent
GITMODULES = ROOT / ".gitmodules"
PACKAGES_YAML = ROOT / "packages.yaml"


def parse_gitmodules(path: Path) -> list[dict]:
    parser = configparser.ConfigParser()
    parser.read(path)
    modules = []
    for section in parser.sections():
        name = section.removeprefix('submodule "').removesuffix('"')
        modules.append(
            {
                "name": name,
                "path": parser[section].get("path", ""),
                "url": parser[section].get("url", ""),
            }
        )
    return modules


def fetch_tags(url: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"  warning: failed to fetch tags from {url}", file=sys.stderr)
            return []
        tags = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            ref = parts[1]
            if ref.endswith("^{}"):
                continue
            tags.append(ref.removeprefix("refs/tags/"))
        return tags
    except subprocess.TimeoutExpired:
        print(f"  warning: timeout fetching tags from {url}", file=sys.stderr)
        return []


def latest_semver(tags: list[str]) -> str | None:
    """Return the tag string with the highest semver, or None if no semver tags found."""
    best_tag = None
    best_tuple = (-1, -1, -1)
    for tag in tags:
        m = SEMVER_RE.match(tag)
        if not m:
            continue
        t = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if t > best_tuple:
            best_tuple = t
            best_tag = tag
    return best_tag


def detect_license(repo: Path) -> str | None:
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        f = repo / name
        if not f.exists():
            continue
        first = (
            f.read_text(errors="replace").lstrip().splitlines()[0]
            if f.stat().st_size
            else ""
        )
        for needle, spdx in LICENSE_MAP:
            if needle.lower() in first.lower():
                return spdx
    return None


def detect_build_system(repo: Path) -> str | None:
    if (repo / "CMakeLists.txt").exists():
        return "cmake"
    if (repo / "meson.build").exists():
        return "meson"
    if (repo / "configure.ac").exists():
        return "autotools"
    if (repo / "Makefile").exists():
        return "make"
    return None


def extract_cmake_info(cmake_text: str) -> dict:
    info: dict = {}

    # project(NAME ... DESCRIPTION "...") — may span lines
    desc_m = re.search(
        r'project\s*\([^)]*DESCRIPTION\s+"([^"]+)"', cmake_text, re.DOTALL
    )
    if desc_m:
        info["summary"] = desc_m.group(1)

    # pkg_check_modules(VAR REQUIRED ... pkg1 pkg2>=x ...)
    deps: list[str] = []
    for m in PKG_CHECK_RE.finditer(cmake_text):
        tokens = m.group(1).split()
        for i, tok in enumerate(tokens):
            if i == 0:  # variable name
                continue
            pkg = re.sub(r"[><=!]+.*$", "", tok)  # strip version constraint
            if not pkg or pkg in CMAKE_KEYWORDS:
                continue
            if re.match(r"^[a-z][a-z0-9\-\.]*$", pkg):
                deps.append(pkg)
    if deps:
        info["pkg_deps"] = deps

    return info


def extract_version(repo: Path) -> str | None:
    version_file = repo / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return None


def resolve_module(modules: list[dict], name: str) -> dict | None:
    """Find a module whose path's last component matches name (case-insensitive)."""
    name_lower = name.lower()
    for mod in modules:
        if Path(mod["path"]).name.lower() == name_lower:
            return mod
    return None


def build_url_to_all_tags(modules: list[dict]) -> dict[str, list[str]]:
    """Fetch all tags for all submodules, return {url: [tag, ...]}."""
    url_to_tags = {}
    for mod in modules:
        name = mod["name"]
        url = mod["url"]
        print(f"fetching tags: {name} ...", file=sys.stderr)
        url_to_tags[url] = fetch_tags(url)
    return url_to_tags


def update_packages_yaml(
    path: Path, url_to_latest: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """
    Update version fields in packages.yaml in-place, preserving comments and formatting.
    Returns {pkg_name: (old_version, new_version)} for changed packages.
    """
    data = yaml.safe_load(path.read_text())
    # Build pkg_name -> new_version using URL matching
    pkg_to_new = {}
    for pkg_name, pkg_data in data.get("packages", {}).items():
        pkg_url = pkg_data.get("url", "")
        new_ver = url_to_latest.get(pkg_url)
        if new_ver and new_ver != str(pkg_data.get("version", "")):
            pkg_to_new[pkg_name] = (str(pkg_data["version"]), new_ver)

    if not pkg_to_new:
        return {}

    # Text pass: preserve comments/formatting, replace only version lines
    lines = path.read_text().splitlines(keepends=True)
    result = []
    current_pkg = None
    for line in lines:
        hdr = PKG_HEADER_RE.match(line)
        if hdr:
            current_pkg = hdr.group(1)

        if current_pkg in pkg_to_new:
            vm = VERSION_LINE_RE.match(line)
            if vm:
                _, new_ver = pkg_to_new[current_pkg]
                line = f'    version: "{new_ver}"\n'

        result.append(line)

    path.write_text("".join(result))
    return pkg_to_new


def cmd_list_tags(modules: list[dict]) -> None:
    """Print all tags for each submodule, marking the detected latest."""
    url_to_tags = build_url_to_all_tags(modules)
    for mod in modules:
        name = mod["name"]
        url = mod["url"]
        tags = url_to_tags.get(url, [])
        detected = latest_semver(tags)
        print(f"\n{name}  ({url})")
        if not tags:
            print("  (no tags found)")
            continue
        for tag in sorted(tags):
            marker = "  <- latest" if tag == detected else ""
            print(f"  {tag}{marker}")


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

    # Check for existing entry
    if PACKAGES_YAML.exists():
        data = yaml.safe_load(PACKAGES_YAML.read_text()) or {}
        if key in data.get("packages", {}):
            print(f"error: '{key}' already exists in packages.yaml", file=sys.stderr)
            sys.exit(1)

    # --- extract info ---
    version = extract_version(repo)
    if version is None:
        print(f"fetching tags to determine version: {key} ...", file=sys.stderr)
        tags = fetch_tags(url)
        latest = latest_semver(tags)
        version = latest.lstrip("v") if latest else "FIXME"

    build_system = detect_build_system(repo) or "FIXME"
    license_id = detect_license(repo) or "FIXME"

    summary = "FIXME"
    pkg_deps: list[str] = []
    cmake = repo / "CMakeLists.txt"
    if cmake.exists():
        cmake_info = extract_cmake_info(cmake.read_text(errors="replace"))
        summary = cmake_info.get("summary", "FIXME")
        pkg_deps = cmake_info.get("pkg_deps", [])

    # Build build_requires list
    build_requires: list[str] = []
    if build_system == "cmake":
        build_requires += ["cmake", "ninja-build", "gcc-c++"]
    elif build_system == "meson":
        build_requires += ["meson", "ninja-build", "gcc-c++"]
    for dep in pkg_deps:
        build_requires.append(f"pkgconfig({dep})")

    # Compose the YAML block as text to preserve formatting
    lines = [
        f"\n  {key}:\n",
        f'    version: "{version}"\n',
        f'    release: "%autorelease"\n',  # noqa: F541
        f"    license: {license_id}\n",
        f"    summary: {summary}\n",
        f"    description: |\n",  # noqa: F541
        f"      FIXME\n",  # noqa: F541
        f"    url: {url}\n",
        f"    sources:\n",  # noqa: F541
        f'      - url: "%{url}/archive/refs/tags/v%{version}.tar.gz"\n',
        f"    build_system: {build_system}\n",
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


def cmd_update(modules: list[dict]) -> None:
    """Fetch latest tags and update packages.yaml."""
    url_to_tags = {mod["url"]: fetch_tags(mod["url"]) for mod in modules}
    url_to_latest: dict[str, str] = {}
    for mod in modules:
        tags = url_to_tags[mod["url"]]
        latest = latest_semver(tags)
        if latest:
            url_to_latest[mod["url"]] = latest.lstrip("v")

    # Print summary YAML to stdout
    summary = {}
    for mod in modules:
        latest = url_to_latest.get(mod["url"])
        summary[mod["name"]] = {"url": mod["url"], "latest": latest}
    print(
        yaml.dump(summary, default_flow_style=False, sort_keys=True, allow_unicode=True)
    )

    if not PACKAGES_YAML.exists():
        print(f"warning: {PACKAGES_YAML} not found, skipping update", file=sys.stderr)
        return

    changed = update_packages_yaml(PACKAGES_YAML, url_to_latest)
    if changed:
        print("updated packages.yaml:", file=sys.stderr)
        for pkg, (old, new) in sorted(changed.items()):
            print(f"  {pkg}: {old} -> {new}", file=sys.stderr)
    else:
        print("packages.yaml: all versions already up to date", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage submodule tags and package versions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s list-tags                  # all submodules\n"
            "  %(prog)s list-tags hyprpicker        # one submodule\n"
            "  %(prog)s update                      # update packages.yaml\n"
            "  %(prog)s add hyprpicker              # scaffold new entry\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    p_list = subparsers.add_parser(
        "list-tags",
        help="show all tags for each submodule and highlight the detected latest",
    )
    p_list.add_argument(
        "package",
        nargs="?",
        metavar="PACKAGE",
        help="limit to this submodule (matches last path component, e.g. hyprpicker)",
    )

    subparsers.add_parser(
        "update",
        help="fetch latest semver tags and update versions in packages.yaml",
    )

    p_add = subparsers.add_parser(
        "add",
        help="scaffold a new packages.yaml entry from a submodule repo",
    )
    p_add.add_argument(
        "package", metavar="PACKAGE", help="submodule name, e.g. hyprpicker"
    )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)

    if args.command == "list-tags":
        if args.package:
            mod = resolve_module(modules, args.package)
            if mod is None:
                print(
                    f"error: submodule '{args.package}' not found in .gitmodules",
                    file=sys.stderr,
                )
                sys.exit(1)
            cmd_list_tags([mod])
        else:
            cmd_list_tags(modules)
    elif args.command == "update":
        cmd_update(modules)
    elif args.command == "add":
        cmd_add(modules, args.package)


if __name__ == "__main__":
    main()
