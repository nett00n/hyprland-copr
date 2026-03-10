"""YAML loading/saving utilities for packages.yaml and build-status.yaml."""

import sys
import time
from pathlib import Path

import yaml

from .paths import GROUPS_YAML, LOG_DIR, PACKAGES_YAML, REPO_YAML

BUILD_STATUS_YAML = LOG_DIR / "build-status.yaml"
STAGES = ["validate", "spec", "vendor", "srpm", "mock", "copr"]


def find_package_name(packages: dict, query: str) -> str | None:
    """Case-insensitive lookup: return the actual key matching query, or None."""
    query_lower = query.lower()
    for name in packages:
        if name.lower() == query_lower:
            return name
    return None


def filter_packages(all_packages: dict, package_env: str) -> dict:
    """Parse PACKAGE env var, resolve names case-insensitively, return filtered dict.

    Exits with error if any name cannot be resolved.
    """
    if not package_env:
        return all_packages
    names = [n.strip() for n in package_env.split(",") if n.strip()]
    resolved: dict[str, dict] = {}
    unknown: list[str] = []
    for n in names:
        key = find_package_name(all_packages, n)
        if key is None:
            unknown.append(n)
        else:
            resolved[key] = all_packages[key]
    if unknown:
        sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
    return resolved


def load_packages_yaml(path: Path = PACKAGES_YAML) -> dict:
    """Load packages.yaml and return the full dict."""
    if not path.exists():
        sys.exit(f"error: {path} not found")
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        sys.exit(f"error: failed to parse {path}: {e}")


def load_repo_yaml(path: Path = REPO_YAML) -> dict:
    """Load repo.yaml and return the full dict."""
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        sys.exit(f"error: failed to parse {path}: {e}")


def load_groups_yaml(path: Path = GROUPS_YAML) -> dict:
    """Load groups.yaml and return the full dict."""
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        sys.exit(f"error: failed to parse {path}: {e}")


def validate_packages(packages: dict) -> None:
    """Validate packages structure and required fields.

    Exits with error if validation fails.
    """
    if not isinstance(packages, dict):
        sys.exit(f"error: packages.yaml root must be a dict, got {type(packages).__name__}")
    for pkg_name, pkg_data in packages.items():
        if not isinstance(pkg_data, dict):
            sys.exit(f"error: package '{pkg_name}' must be a dict, got {type(pkg_data).__name__}")
        if "version" not in pkg_data:
            sys.exit(f"error: package '{pkg_name}' missing required field 'version'")


def get_packages(path: Path = PACKAGES_YAML) -> dict:
    """Return the packages dict from packages.yaml (packages at root level)."""
    data = load_packages_yaml(path)
    packages = data or {}
    if not packages:
        sys.exit("error: no packages defined in packages.yaml")
    validate_packages(packages)
    return packages


# Alias for compatibility
load_packages = get_packages

SUPPORTED_FEDORA_VERSIONS = {"43", "44", "rawhide"}
OVERRIDE_LIST_FIELDS = {"build_requires", "requires"}
OVERRIDE_BUILD_SUBKEYS = {"prep", "commands", "install"}
OVERRIDE_SOURCE_SUBKEYS = {"patches"}


def apply_os_overrides(pkg: dict, fedora_version: str) -> dict:
    """Apply fedora-version-specific overrides to a package dict.

    Returns a new dict with overrides applied, or the original if no overrides.
    Sets pkg["_skip"] = True if this version should be skipped.
    """
    fedora_blocks = pkg.get("fedora", {})
    if not fedora_blocks:
        return pkg

    # Try exact string match first (for "rawhide"), then int match
    override = fedora_blocks.get(fedora_version) or fedora_blocks.get(
        int(fedora_version) if fedora_version.isdigit() else None
    )
    if override is None:
        result = {k: v for k, v in pkg.items() if k != "fedora"}
        return result

    result = {k: v for k, v in pkg.items() if k != "fedora"}

    if override.get("skip"):
        result["_skip"] = True
        return result

    for field in OVERRIDE_LIST_FIELDS:
        if field in override:
            result[field] = override[field]

    if "build" in override:
        build_override = override["build"]
        merged_build = dict(result.get("build") or {})
        for subkey in OVERRIDE_BUILD_SUBKEYS:
            if subkey in build_override:
                merged_build[subkey] = build_override[subkey]
        result["build"] = merged_build

    if "source" in override:
        source_override = override["source"]
        merged_source = dict(result.get("source") or {})
        for subkey in OVERRIDE_SOURCE_SUBKEYS:
            if subkey in source_override:
                merged_source[subkey] = source_override[subkey]
        result["source"] = merged_source

    return result


def get_active_packages(fedora_version: str, path: Path = PACKAGES_YAML) -> dict:
    """Return packages dict with OS overrides applied and skipped packages removed."""
    packages = get_packages(path)
    result = {}
    for name, pkg in packages.items():
        resolved = apply_os_overrides(pkg, fedora_version)
        if resolved.get("_skip"):
            continue
        result[name] = resolved
    return result


def load_build_status(path: Path = BUILD_STATUS_YAML) -> dict:
    """Load build-status.yaml or return empty structure."""
    if path.exists():
        try:
            return yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as e:
            sys.exit(f"error: failed to parse {path}: {e}")
    return {"stages": {s: {} for s in STAGES}}


def save_build_status(status: dict, path: Path = BUILD_STATUS_YAML) -> None:
    """Save build-status.yaml, creating parent dirs if needed."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        yaml.dump(status, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


def pop_build_stages(
    pkgs: list[str] | set[str],
    stages: tuple[str, ...] = ("mock", "copr"),
) -> list[str]:
    """Remove entries for pkgs from given stages in build-status.yaml.

    Returns sorted list of package names that were actually removed.
    """
    build_status = load_build_status()
    status_stages = build_status.get("stages", {})
    affected: set[str] = set()
    for stage in stages:
        stage_data = status_stages.get(stage, {})
        for pkg in pkgs:
            if stage_data.pop(pkg, None) is not None:
                affected.add(pkg)
    save_build_status(build_status)
    return sorted(affected)


def now_epoch() -> int:
    """Return current Unix timestamp as integer."""
    return int(time.time())


def stage_was_success(build_status: dict, stage: str, pkg: str) -> bool:
    """Check if a package succeeded in a given stage."""
    return (
        build_status.get("stages", {}).get(stage, {}).get(pkg, {}).get("state")
        == "success"
    )


def write_yaml_preserving_comments(
    path: Path,
    url_to_latest: dict[str, str],
    url_to_commit_info: dict[str, tuple[str, str, str]] | None = None,
) -> dict[str, tuple[str, str]]:
    """Update version/commit fields in packages.yaml using yaml load/dump.

    Comments will not be preserved (accepted trade-off for simpler code).
    Returns {pkg_name: (old_version, new_version)} for changed packages.
    """
    if url_to_commit_info is None:
        url_to_commit_info = {}

    data = yaml.safe_load(path.read_text())
    changed: dict[str, tuple[str, str]] = {}

    for pkg_name, pkg_data in data.items():
        pkg_url = pkg_data.get("url", "")
        current_ver = str(pkg_data.get("version", ""))

        new_ver = url_to_latest.get(pkg_url)
        if new_ver and new_ver != current_ver:
            pkg_data["version"] = new_ver
            changed[pkg_name] = (current_ver, new_ver)
        elif pkg_url in url_to_commit_info:
            source = pkg_data.get("source", {})
            if source.get("commit"):
                full_hash, short_hash, date_str = url_to_commit_info[pkg_url]
                new_commit_ver = f"0^{date_str}git{short_hash}"
                if new_commit_ver != current_ver:
                    pkg_data["version"] = new_commit_ver
                    source["commit"]["full"] = full_hash
                    source["commit"]["date"] = date_str
                    changed[pkg_name] = (current_ver, new_commit_ver)

    if changed:
        path.write_text(
            yaml.dump(
                data, default_flow_style=False, sort_keys=False, allow_unicode=True
            )
        )
    return changed
