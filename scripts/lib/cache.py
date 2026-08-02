"""Build input hash computation for skip-if-unchanged cache logic."""

import hashlib
import json

from lib.deps import effective_deps
from lib.paths import ROOT, TEMPLATE_DIR


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


# release_types whose build actually downloads a specific commit's tarball (the
# archive URL is templated as `%{url}/archive/%{commit}.tar.gz`, with
# source.commit.full written by update-versions.py). Every other release_type
# builds from a fixed version/tag tarball URL that has no commit in it at all.
_COMMIT_TRACKED_RELEASE_TYPES = {"latest-commit", "pinned-commit"}


def _source_commit(pkg: str, meta: dict) -> str | None:
    """Return the commit hash this package's build downloads, or None.

    Read from packages.yaml `source.commit.full` -- the exact value the spec
    expands into `%{commit}`, and therefore the only commit the build ever
    sees. Deliberately NOT read from the submodule checkout: the checkout is
    not a build input at all (spectool downloads the archive over the network),
    so hashing it just made the cache depend on wherever update-versions.py
    last left the working tree -- including a nightly submodule pull that
    moves every submodule to upstream HEAD regardless of this package's own
    release_type (see docs/bugs.md BUG-0033).

    Only meaningful for packages in _COMMIT_TRACKED_RELEASE_TYPES (see above)
    -- for everyone else, including a commit in the input hashes just forces
    an unrelated full rebuild+resubmit with an unchanged version (see
    docs/bugs.md BUG-0034). Returns None for a commit-tracked package with no
    source.commit yet (e.g. a mis-shaped package whose archive URL is keyed on
    %{version} instead of %{commit}) -- already covered by the
    package_version input hash.
    """
    release_type = (meta.get("auto_update") or {}).get("release_type")
    if release_type not in _COMMIT_TRACKED_RELEASE_TYPES:
        return None
    commit = ((meta.get("source") or {}).get("commit") or {}).get("full")
    return str(commit) if commit else None


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
