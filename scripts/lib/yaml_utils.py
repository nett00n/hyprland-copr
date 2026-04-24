"""YAML loading/saving utilities for packages.yaml and build-report.yaml."""

import os
import sys
import time
from pathlib import Path
from typing import Literal, overload

import yaml

from .paths import (
    BUILD_LOG_DIR,
    BUILD_STATUS_YAML,
    GROUPS_YAML,
    PACKAGES_YAML,
    REPO_YAML,
)
from .yaml_config import DEFAULT as DEFAULT_YAML_CONFIG

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


def skip_packages(packages: dict, skip_env: str) -> dict:
    """Parse SKIP_PACKAGES env var, remove matching packages case-insensitively.

    Returns dict with excluded packages removed. No error if packages don't exist.
    """
    if not skip_env:
        return packages
    names = [n.strip().lower() for n in skip_env.split(",") if n.strip()]
    skip_set = set(names)
    return {k: v for k, v in packages.items() if k.lower() not in skip_set}


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
        sys.exit(
            f"error: packages.yaml root must be a dict, got {type(packages).__name__}"
        )
    for pkg_name, pkg_data in packages.items():
        if not isinstance(pkg_data, dict):
            sys.exit(
                f"error: package '{pkg_name}' must be a dict, got {type(pkg_data).__name__}"
            )
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


def load_build_status(path: Path = BUILD_STATUS_YAML) -> dict:
    """Load build-report.yaml or return empty structure."""
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text())
            if not isinstance(data, dict):
                # Non-dict content, use default structure
                data = {}
        except yaml.YAMLError as e:
            sys.exit(f"error: failed to parse {path}: {e}")
    else:
        data = {}

    # Normalize: ensure stages key exists
    if "stages" not in data:
        data["stages"] = {s: {} for s in STAGES}

    return data


def dump_yaml_pretty(data: dict) -> str:
    """Dump YAML data in pretty format matching yamllint defaults."""
    return DEFAULT_YAML_CONFIG.dump(data)


def save_build_status(status: dict, path: Path = BUILD_STATUS_YAML) -> None:
    """Save build-report.yaml, creating parent dirs if needed."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(dump_yaml_pretty(status))


def pop_build_stages(
    pkgs: list[str] | set[str],
    stages: tuple[str, ...] = ("mock", "copr"),
) -> list[str]:
    """Set force_run: true flag for pkgs in given stages in build-report.yaml.

    Returns sorted list of package names that were affected.
    """
    build_status = load_build_status()
    status_stages = build_status.get("stages", {})
    affected: set[str] = set()
    for stage in stages:
        if stage not in status_stages:
            status_stages[stage] = {}
        stage_data = status_stages[stage]
        for pkg in pkgs:
            if pkg in stage_data:
                stage_data[pkg]["force_run"] = True
                affected.add(pkg)
    save_build_status(build_status)
    return sorted(affected)


def now_epoch() -> int:
    """Return current Unix timestamp as integer."""
    return int(time.time())


@overload
def init_stage(
    stage_name: str, include_all: Literal[False] = False
) -> tuple[dict, dict]: ...


@overload
def init_stage(
    stage_name: str, include_all: Literal[True]
) -> tuple[dict, dict, dict]: ...


def init_stage(  # type: ignore
    stage_name: str, include_all: bool = False
) -> tuple[dict, dict] | tuple[dict, dict, dict]:
    """Initialize a stage with standard boilerplate.

    Returns (packages, build_status) after filtering and initialization.
    If include_all=True, returns (all_packages, packages, build_status).
    """
    package_env = os.environ.get("PACKAGE", "")
    skip_env = os.environ.get("SKIP_PACKAGES", "")
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    all_packages = get_packages()
    packages = filter_packages(all_packages, package_env)
    packages = skip_packages(packages, skip_env)

    BUILD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    build_status = load_build_status()
    # Only clear stage if NOT resuming (PROCEED_BUILD=false)
    if not proceed:
        build_status.setdefault("stages", {})[stage_name] = {}
    else:
        build_status.setdefault("stages", {}).setdefault(stage_name, {})

    if include_all:
        return all_packages, packages, build_status
    return packages, build_status


def write_yaml_preserving_comments(
    path: Path,
    url_to_latest: dict[str, str],
    url_to_commit_info: dict[str, tuple[str, str, str, str | None]] | None = None,
) -> dict[str, tuple[str, str]]:
    """Update version/commit fields in packages.yaml using yaml load/dump.

    Comments will not be preserved (accepted trade-off for simpler code).
    When version changes, also sets release=0 to signal autoreset in next pre-build step.
    Returns {pkg_name: (old_version, new_version)} for changed packages.

    url_to_commit_info values are 4-tuples: (full_hash, short_hash, date_YYYYMMDD, base_semver | None)
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
            pkg_data["release"] = 0  # Reset release on version change
            changed[pkg_name] = (current_ver, new_ver)
        elif pkg_url in url_to_commit_info:
            full_hash, short_hash, date_str, base_semver = url_to_commit_info[pkg_url]
            prefix = base_semver if base_semver else "0"
            new_commit_ver = f"{prefix}^{date_str}git{short_hash}"

            # Check if this is a latest-commit or pinned-tag release_type
            auto_update = pkg_data.get("auto_update", {})
            release_type = auto_update.get("release_type", "")
            should_create_commit = release_type in ("latest-commit", "pinned-tag")

            source = pkg_data.get("source", {})
            if source.get("commit") or should_create_commit:
                if not source.get("commit"):
                    source["commit"] = {}
                if new_commit_ver != current_ver:
                    pkg_data["version"] = new_commit_ver
                    pkg_data["release"] = 0  # Reset release on version change
                    source["commit"]["full"] = full_hash
                    source["commit"]["date"] = date_str
                    changed[pkg_name] = (current_ver, new_commit_ver)
                    if "source" not in pkg_data:
                        pkg_data["source"] = source

    if changed:
        path.write_text(dump_yaml_pretty(data))
    return changed


def update_package_releases(packages: dict, build_status: dict) -> dict[str, int]:
    """Auto-increment or reset release values for packages.

    Pre-build step, called in topological order (packages dict preserves order).

    Rules:
    1. Compute content hash (excludes release field) for current package
    2. Compare against stored content hash + version from last build
    3. If content differs OR force_run set OR dep was rebuilt:
       - Release needs increment (or reset if version changed)
    4. If version changed (or release == 0):
       - Reset to 1
    5. Otherwise:
       - Increment by 1 (with fallback to 1 if int conversion fails)

    Cascade: dependency rebuild forces all dependents to increment.

    Args:
        packages: Dict of {pkg_name: pkg_dict}, in topological order
        build_status: Current build status dict with stored hashes

    Returns:
        Dict of {pkg_name: new_release} for packages that were updated
    """
    from lib.cache import _content_hash

    dep_will_rebuild: set[str] = set()
    updates: dict[str, int] = {}

    for pkg_name, pkg_dict in packages.items():
        # Skip auto-management if release_lock is set
        if pkg_dict.get("release_lock"):
            continue
        # Compute content hash (excludes release)
        content_hash = _content_hash(pkg_dict)

        # Read stored state
        last_entry = build_status.get("stages", {}).get("spec", {}).get(pkg_name, {})
        stored_hashes = last_entry.get("hashes", {})
        last_content_hash = stored_hashes.get("content")
        last_version = stored_hashes.get("package_version")

        # Check for force_run in any stage
        force_run = any(
            build_status.get("stages", {})
            .get(stage, {})
            .get(pkg_name, {})
            .get("force_run", False)
            for stage in ["validate", "spec", "vendor", "srpm", "mock", "copr"]
        )

        # Check if any dependency was marked for rebuild
        dep_cascade = any(
            dep in dep_will_rebuild for dep in pkg_dict.get("depends_on", [])
        )

        # Determine if this package needs rebuild
        needs_rebuild = (
            last_content_hash is None  # first run or no stored content
            or content_hash != last_content_hash
            or force_run
            or dep_cascade
        )

        if needs_rebuild:
            dep_will_rebuild.add(pkg_name)

            # Determine new release value
            current_release = pkg_dict.get("release", 1)
            version_changed = (
                last_version is None or str(pkg_dict.get("version", "")) != last_version
            )

            if version_changed or current_release == 0:
                new_release = 1
            else:
                # Try to increment; fallback to 1 on error
                try:
                    new_release = int(current_release) + 1
                except (ValueError, TypeError):
                    new_release = 1

            # Only record update if release value actually changed
            if new_release != current_release:
                updates[pkg_name] = new_release

    # Write updates back to packages.yaml if any
    if updates:
        data = yaml.safe_load(PACKAGES_YAML.read_text())
        for pkg_name, new_release in updates.items():
            if pkg_name in data:
                data[pkg_name]["release"] = new_release
        PACKAGES_YAML.write_text(dump_yaml_pretty(data))

    return updates
