"""Build input hash computation for skip-if-unchanged cache logic."""

import hashlib
import json
from typing import Any

from lib.deps import effective_deps
from lib.paths import ROOT, TEMPLATE_DIR
from lib.version import COMMIT_TRACKED_RELEASE_TYPES


def _sha256(content: bytes) -> str:
    """Compute SHA256 hash of content and return hex digest."""
    return hashlib.sha256(content).hexdigest()


def _normalize_keys(obj: Any) -> Any:
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
    """Return the commit hash this package's build downloads, or None.

    Read from packages.yaml `source.commit.full` -- the exact value the spec
    expands into `%{commit}`, and therefore the only commit the build ever
    sees. Deliberately NOT read from the submodule checkout: the checkout is
    not a build input at all (spectool downloads the archive over the network),
    so hashing it just made the cache depend on wherever update-versions.py
    last left the working tree -- including a nightly submodule pull that
    moves every submodule to upstream HEAD regardless of this package's own
    release_type (see docs/BUGS.md BUG-0033).

    Only meaningful for packages in lib.version.COMMIT_TRACKED_RELEASE_TYPES
    -- for everyone else, including a commit in the input hashes just forces
    an unrelated full rebuild+resubmit with an unchanged version (see
    docs/BUGS.md BUG-0034). Returns None for a commit-tracked package with no
    source.commit yet (e.g. a mis-shaped package whose archive URL is keyed on
    %{version} instead of %{commit}) -- already covered by the
    package_version input hash.
    """
    release_type = (meta.get("auto_update") or {}).get("release_type")
    if release_type not in COMMIT_TRACKED_RELEASE_TYPES:
        return None
    commit = ((meta.get("source") or {}).get("commit") or {}).get("full")
    return str(commit) if commit else None


def _templates_hash() -> str:
    """Return SHA256 hash of spec.j2 template."""
    return _sha256((TEMPLATE_DIR / "spec.j2").read_bytes())


# #COPR-0002, #COPR-0005, #BUG-0058: the generator's own source, hashed rather than
# hand-maintained as a version constant nobody remembers to bump. stage-spec.py is
# the generator the pipeline actually uses (see COPR-0005 Quirks) -- gen-spec.py is
# separate, unused dead code tracked by BUG-0074, deliberately not included here.
_GENERATOR_FILES = ("stage-spec.py", "lib/spec_utils.py")


def _generator_hash() -> str:
    """Return a combined SHA256 hash of the spec generator's own source files."""
    h = hashlib.sha256()
    for rel in _GENERATOR_FILES:
        h.update((ROOT / "scripts" / rel).read_bytes())
    return h.hexdigest()


# #BUG-0057, #BUG-0058: these two `compute_input_hashes()` keys are advisory, not
# invalidating -- hashes_match() ignores them, so editing spec.j2 or the generator
# itself never forces a rebuild. stale_advisories() reports the mismatch instead.
ADVISORY_HASH_KEYS = frozenset({"templates", "generator"})


def _dependencies_hashes(pkg: str, meta: dict, all_packages: dict) -> dict[str, str]:
    """Return {dep_name: hash} for each of pkg's effective dependencies.

    Sorted for deterministic dict/YAML key order (effective_deps returns a set).

    #BUG-0098: uses `_content_hash()`, same as this package's own `content` input
    -- `_package_config_hash()` was a byte-identical duplicate (same normalize
    -> exclude-release -> sha256 steps) stored under a second key in every
    stage row and has been removed.
    """
    return {
        dep: _content_hash(all_packages[dep])
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
    - content: hash of package config EXCLUDING release field (stable across release-only
      changes) -- the single "package config hash" implementation; #BUG-0098 removed a
      byte-identical `package_config` key that used to be stored alongside it
    - package_version: current version string (for release autoreset detection)
    """
    return {
        "source_commit": _source_commit(pkg, meta),
        "templates": _templates_hash(),
        "generator": _generator_hash(),
        "dependencies": _dependencies_hashes(pkg, meta, all_packages),
        "patches": _patches_hashes(pkg, meta),
        "content": _content_hash(meta),
        "package_version": str(meta.get("version", "")),
    }


def hashes_match(stored_entry: dict, new_hashes: dict) -> bool:
    """Return True if stored entry's *invalidating* hashes match new_hashes.

    #BUG-0057, #BUG-0058: `ADVISORY_HASH_KEYS` (`templates`, `generator`) are
    excluded from this comparison -- editing spec.j2 or the generator itself
    must not force a rebuild, only get reported via `stale_advisories()`.
    Compares the intersection of *invalidating* keys present on each side: a
    key missing from `stored` (an older schema, or a key added later) counts
    as a mismatch, same as before this changed the dict shape.
    """
    stored = stored_entry.get("hashes")
    if not stored:
        return False
    invalidating = set(new_hashes) - ADVISORY_HASH_KEYS
    return (
        all(stored.get(k, object()) == new_hashes[k] for k in invalidating)
        and set(stored) - ADVISORY_HASH_KEYS == invalidating
    )


def stale_advisories(stored_entry: dict, new_hashes: dict) -> list[str]:
    """Return which advisory inputs changed since `stored_entry` was recorded.

    #BUG-0057, #BUG-0058. Returns a subset of `["stale-template",
    "stale-generator"]`, in that order. A key stored_entry never recorded (an
    older schema, before that advisory existed) is treated as "unknown, not
    stale" -- there's nothing to compare against, and reporting every
    pre-existing row stale on the first run after this shipped would be noise,
    not signal.
    """
    stored = stored_entry.get("hashes") or {}
    stale = []
    if "templates" in stored and stored["templates"] != new_hashes.get("templates"):
        stale.append("stale-template")
    if "generator" in stored and stored["generator"] != new_hashes.get("generator"):
        stale.append("stale-generator")
    return stale
