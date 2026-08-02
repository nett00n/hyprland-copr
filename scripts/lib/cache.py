"""Build input hash computation for skip-if-unchanged cache logic."""

import hashlib
import json

from lib.deps import effective_deps
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


# release_types whose build actually tracks the submodule's live commit (the
# archive URL is templated as `%{url}/archive/%{commit}.tar.gz`, refreshed
# from the checkout by update-versions.py each run). Every other release_type
# builds from a fixed version/tag tarball URL that never reads the checkout.
_COMMIT_TRACKED_RELEASE_TYPES = {"latest-commit", "pinned-commit"}


def _source_commit(pkg: str, meta: dict) -> str | None:
    """Return full git commit hash of the package's submodule, or None.

    Only meaningful for packages in _COMMIT_TRACKED_RELEASE_TYPES (see above)
    -- for everyone else, including this in the input hashes just means a
    nightly submodule pull (which moves every submodule to upstream HEAD,
    regardless of this package's own release_type) forces an unrelated full
    rebuild+resubmit with an unchanged version (see docs/bugs.md BUG-0034).

    First tries to match by package name. If not found, falls back to the source.name
    field (used for packages like Hyprland-git that track a different repo).
    """
    release_type = meta.get("auto_update", {}).get("release_type")
    if release_type not in _COMMIT_TRACKED_RELEASE_TYPES:
        return None
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
    """Return SHA256 hash of a package's configuration entry.

    Excludes 'release' field so that release-only changes in dependencies
    don't trigger cascade rebuilds of dependents.
    """
    # Exclude release field to prevent unnecessary cascades
    config = {k: v for k, v in entry.items() if k != "release"}
    normalized = _normalize_keys(config)
    return _sha256(json.dumps(normalized, sort_keys=True, default=str).encode())


def _dependencies_hashes(pkg: str, meta: dict, all_packages: dict) -> dict[str, str]:
    """Return {dep_name: hash} for each of pkg's effective dependencies.

    Sorted for deterministic dict/YAML key order (effective_deps returns a set).
    """
    return {
        dep: _package_config_hash(all_packages[dep])
        for dep in sorted(effective_deps(pkg, meta, all_packages))
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
        "dependencies": _dependencies_hashes(pkg, meta, all_packages),
        "patches": _patches_hashes(pkg, meta),
        "content": _content_hash(meta),
        "package_version": str(meta.get("version", "")),
    }


def hashes_match(stored_entry: dict, new_hashes: dict) -> bool:
    """Return True if stored entry's hashes match new_hashes exactly."""
    stored = stored_entry.get("hashes")
    return bool(stored) and stored == new_hashes
