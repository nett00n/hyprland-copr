"""YAML loading/saving utilities for packages.yaml and build-status.yaml."""

import re
import sys
from pathlib import Path

import yaml

from .paths import LOG_DIR, PACKAGES_YAML

# Regex constants for text-level YAML editing (preserve comments/formatting)
PKG_HEADER_RE = re.compile(r"^  (\w[\w\-]+):\s*(?:#.*)?$")
VERSION_LINE_RE = re.compile(r'^    version: "([^"]+)"')
COMMIT_FULL_RE = re.compile(r"^      full: ([a-f0-9]+)\s*$")
COMMIT_DATE_RE = re.compile(r'^      date: "(\d+)"\s*$')
PKG_URL_LINE_RE = re.compile(r"^    url: \S+")
SOURCE_TAG_URL_RE = re.compile(r'^      - url: ".*?/archive/refs/tags/.*?"')

BUILD_STATUS_YAML = LOG_DIR / "build-status.yaml"
STAGES = ["spec", "srpm", "mock", "copr"]


def load_packages_yaml(path: Path = PACKAGES_YAML) -> dict:
    """Load packages.yaml and return the full dict."""
    if not path.exists():
        sys.exit(f"error: {path} not found")
    return yaml.safe_load(path.read_text()) or {}


def get_packages(path: Path = PACKAGES_YAML) -> dict:
    """Return the packages dict from packages.yaml."""
    data = load_packages_yaml(path)
    packages = data.get("packages") or {}
    if not packages:
        sys.exit("error: no packages defined in packages.yaml")
    return packages


# Alias for compatibility
load_packages = get_packages


def load_build_status(path: Path = BUILD_STATUS_YAML) -> dict:
    """Load build-status.yaml or return empty structure."""
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}
    return {"stages": {s: {} for s in STAGES}}


def save_build_status(status: dict, path: Path = BUILD_STATUS_YAML) -> None:
    """Save build-status.yaml, creating parent dirs if needed."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        yaml.dump(status, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


def write_yaml_preserving_comments(
    path: Path,
    url_to_latest: dict[str, str],
    url_to_commit_info: dict[str, tuple[str, str, str]] | None = None,
) -> dict[str, tuple[str, str]]:
    """Update version fields in packages.yaml in-place, preserving comments/formatting.

    url_to_latest: {url: new_version_string}
    url_to_commit_info: {url: (full_hash, short_hash, date_str)} for no-tag packages.
    Only updates commit block fields when a commit: block already exists in the entry.
    Returns {pkg_name: (old_version, new_version)} for changed packages.
    """
    if url_to_commit_info is None:
        url_to_commit_info = {}

    data = yaml.safe_load(path.read_text())
    pkg_to_new: dict[str, tuple[str, str]] = {}
    pkg_to_commit: dict[str, tuple[str, str, str, str]] = {}

    for pkg_name, pkg_data in data.get("packages", {}).items():
        pkg_url = pkg_data.get("url", "")
        new_ver = url_to_latest.get(pkg_url)
        if new_ver and new_ver != str(pkg_data.get("version", "")):
            pkg_to_new[pkg_name] = (str(pkg_data["version"]), new_ver)
        elif pkg_url in url_to_commit_info and pkg_data.get("commit"):
            full_hash, short_hash, date_str = url_to_commit_info[pkg_url]
            new_commit_ver = f"0^{date_str}git{short_hash}"
            current_ver = str(pkg_data.get("version", ""))
            if new_commit_ver != current_ver:
                pkg_to_commit[pkg_name] = (
                    current_ver,
                    new_commit_ver,
                    full_hash,
                    date_str,
                )

    if not pkg_to_new and not pkg_to_commit:
        return {}

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

        if current_pkg in pkg_to_commit:
            _, new_ver, full_hash, date_str = pkg_to_commit[current_pkg]
            if VERSION_LINE_RE.match(line):
                line = f'    version: "{new_ver}"\n'
            elif COMMIT_FULL_RE.match(line):
                line = f"      full: {full_hash}\n"
            elif COMMIT_DATE_RE.match(line):
                line = f'      date: "{date_str}"\n'

        result.append(line)

    path.write_text("".join(result))
    changed: dict[str, tuple[str, str]] = {}
    changed.update(pkg_to_new)
    changed.update({k: (old, new) for k, (old, new, _, _) in pkg_to_commit.items()})
    return changed
