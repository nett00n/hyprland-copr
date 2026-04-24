"""Build input hash computation for skip-if-unchanged cache logic."""

import hashlib
import json

from lib.gitmodules import parse_gitmodules, resolve_module, get_submodule_commit
from lib.paths import GITMODULES, ROOT, TEMPLATE_DIR


def _sha256(content: bytes) -> str:
    """Compute SHA256 hash of content and return hex digest."""
    return hashlib.sha256(content).hexdigest()


def _normalize_keys(obj):
    """Recursively convert all dict keys to strings for consistent serialization."""
    if isinstance(obj, dict):
        return {str(k): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    return obj


def _content_hash(pkg_dict: dict) -> str:
    """Compute SHA256 hash of package dict WITHOUT release field.

    Represents "real content" (version, build config, etc.) decoupled from
    release counter. Excludes 'release' key so that release-only changes
    don't trigger rebuilds.
    """
    # Copy dict, exclude release
    content = {k: v for k, v in pkg_dict.items() if k != "release"}
    normalized = _normalize_keys(content)
    return _sha256(json.dumps(normalized, sort_keys=True, default=str).encode())


def _source_commit(pkg: str, meta: dict) -> str | None:
    """Return full git commit hash of the package's submodule, or None if not found.

    First tries to match by package name. If not found, falls back to the source.name
    field (used for packages like Hyprland-git that track a different repo).
    """
    modules = parse_gitmodules(GITMODULES)
    mod = resolve_module(modules, pkg)
    # Fallback: try source.name (e.g., Hyprland-git with source.name: Hyprland)
    if mod is None:
        source_name = meta.get("source", {}).get("name", "")
        if source_name:
            mod = resolve_module(modules, source_name)
    if mod is None:
        return None
    result = get_submodule_commit(ROOT / mod["path"])
    return result[0] if result else None  # full hash


def _templates_hash() -> str:
    """Return SHA256 hash of spec.j2 template."""
    return _sha256((TEMPLATE_DIR / "spec.j2").read_bytes())


def _package_config_hash(entry: dict) -> str:
    """Return SHA256 hash of a package's configuration entry."""
    normalized = _normalize_keys(entry)
    return _sha256(json.dumps(normalized, sort_keys=True, default=str).encode())


def _dependencies_hashes(meta: dict, all_packages: dict) -> dict[str, str]:
    """Return {dep_name: hash} for each dependency in depends_on."""
    return {
        dep: _package_config_hash(all_packages[dep])
        for dep in meta.get("depends_on", [])
        if dep in all_packages
    }


def _patches_hashes(pkg: str, meta: dict) -> dict[str, str | None]:
    """Return {patch_name: hash} for each patch in source.patches."""
    result = {}
    for name in meta.get("source", {}).get("patches", []):
        path = ROOT / "packages" / pkg / name
        result[name] = _sha256(path.read_bytes()) if path.exists() else None
    return result


def compute_input_hashes(pkg: str, meta: dict, all_packages: dict) -> dict:
    """Compute all input hashes for a package: source commit, templates, config, deps, patches.

    Also computes:
    - content: hash of package config EXCLUDING release field (stable across release-only changes)
    - package_version: current version string (for release autoreset detection)
    """
    return {
        "source_commit": _source_commit(pkg, meta),
        "templates": _templates_hash(),
        "package_config": _package_config_hash(meta),
        "dependencies": _dependencies_hashes(meta, all_packages),
        "patches": _patches_hashes(pkg, meta),
        "content": _content_hash(meta),
        "package_version": str(meta.get("version", "")),
    }


def hashes_match(stored_entry: dict, new_hashes: dict) -> bool:
    """Return True if stored entry's hashes match new_hashes exactly."""
    stored = stored_entry.get("hashes")
    return bool(stored) and stored == new_hashes
