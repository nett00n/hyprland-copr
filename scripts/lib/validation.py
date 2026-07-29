"""Package validation utilities.

Validates package.yaml entries, group membership, and .gitmodules conventions.
"""

from lib.gitmodules import parse_gitmodules
from lib.paths import GITMODULES, ROOT
from lib.yaml_utils import SUPPORTED_FEDORA_VERSIONS, load_groups_yaml

REQUIRED_FIELDS = ["version", "license", "summary", "description", "url"]
VALID_BUILD_SYSTEMS = {
    "autotools",
    "cargo",
    "cmake",
    "configure",
    "golang",
    "make",
    "meson",
    "python",
}
DEVEL_INDICATORS = ["%{_includedir}", "pkgconfig/", "/cmake/"]
VALID_FEDORA_OVERRIDE_KEYS = {"skip", "build_requires", "requires", "build"}


def validate_package(
    name: str, meta: dict, all_packages: dict
) -> tuple[list[str], list[str]]:
    """Validate a single package entry.

    Checks:
    - Required fields present and non-empty
    - source.archives present
    - No deprecated sections
    - Valid build system
    - No devel files in main files section
    - depends_on references valid packages
    - build_requires references covered by depends_on
    - fedora: overrides use valid versions and keys

    Args:
        name: Package name
        meta: Package metadata dict
        all_packages: Dict of all packages for cross-validation

    Returns:
        Tuple of (errors, warnings) as lists of strings
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if not meta.get(field):
            errors.append(f"missing required field: {field}")

    # source.archives required
    if not meta.get("source", {}).get("archives"):
        errors.append("missing required field: source.archives")

    # Deprecated debuginfo section
    if "debuginfo" in meta:
        errors.append(
            "deprecated 'debuginfo' section present — rely on RPM auto-generation"
        )

    # build_system validity
    bs = meta.get("build", {}).get("system", "")
    if bs and bs != "FIXME" and bs not in VALID_BUILD_SYSTEMS:
        errors.append(
            f"invalid build_system '{bs}' (must be one of: {', '.join(sorted(VALID_BUILD_SYSTEMS))})"
        )

    # Devel files in wrong place (main files section)
    main_files = meta.get("files", []) or []
    for f in main_files:
        for indicator in DEVEL_INDICATORS:
            if indicator in str(f):
                warnings.append(
                    f"devel path '{f}' found in main files — should be in devel.files"
                )
                break

    # Validate depends_on entries
    pkg_by_lower = {k.lower(): k for k in all_packages}
    depends_on = meta.get("depends_on")
    if depends_on is not None:
        for dep in depends_on:
            if dep.lower() not in pkg_by_lower:
                errors.append(f"depends_on: '{dep}' is not a known package")

    # Warn if build_requires has local refs not covered by depends_on
    depends_on_lower = {d.lower() for d in (depends_on or [])}
    for req in meta.get("build_requires", []) or []:
        if not isinstance(req, str):
            continue
        base: str | None = None
        if req.endswith("-devel"):
            base = req[:-6].lower()
        elif req.startswith("pkgconfig(") and req.endswith(")"):
            base = req[10:-1].lower()
        if base and base in pkg_by_lower and pkg_by_lower[base] != name:
            if base not in depends_on_lower:
                resolved = pkg_by_lower[base]
                warnings.append(
                    f"build_requires '{req}' references local package '{resolved}'"
                    " — add to depends_on"
                )

    # Validate fedora: override blocks
    fedora_blocks = meta.get("fedora", {})
    if fedora_blocks:
        for ver_key, override in fedora_blocks.items():
            ver_str = str(ver_key)
            if ver_str not in SUPPORTED_FEDORA_VERSIONS:
                warnings.append(
                    f"fedora: block '{ver_key}' is not a supported version"
                    f" (supported: {', '.join(sorted(SUPPORTED_FEDORA_VERSIONS))})"
                )
            if not isinstance(override, dict):
                errors.append(f"fedora.{ver_key}: must be a mapping")
                continue
            unknown_keys = set(override) - VALID_FEDORA_OVERRIDE_KEYS
            if unknown_keys:
                errors.append(
                    f"fedora.{ver_key}: unknown override key(s): {', '.join(sorted(unknown_keys))}"
                )

    return errors, warnings


def validate_group_membership(all_packages: dict) -> tuple[list[str], list[str]]:
    """Check every package appears in at least one group's packages list.

    Args:
        all_packages: Dict of all packages

    Returns:
        Tuple of (errors, warnings) as lists of strings
    """
    errors: list[str] = []
    warnings: list[str] = []

    groups = load_groups_yaml()
    grouped: set[str] = set()
    for group_meta in groups.values():
        for pkg in group_meta.get("packages") or []:
            grouped.add(pkg)

    for pkg in all_packages:
        if pkg not in grouped:
            errors.append(f"package '{pkg}' is not listed in any group")

    return errors, warnings


def validate_no_duplicate_urls(all_packages: dict) -> tuple[list[str], list[str]]:
    """Warn when two or more packages declare the exact same url.

    update-versions.py resolves each package's submodule by matching its url;
    a duplicate is legitimate (e.g. a stable package and its "-git" sibling
    tracking the same upstream repo) as long as each package's own
    auto_update.release_type is applied independently. This check exists to
    surface the duplication itself, since an accidental collision (e.g. one
    side losing a distinguishing ".git" suffix) previously let one package's
    auto_update config silently shadow another's version resolution.

    Args:
        all_packages: Dict of all packages

    Returns:
        Tuple of (errors, warnings) as lists of strings — always empty errors
    """
    errors: list[str] = []
    warnings: list[str] = []

    by_url: dict[str, list[str]] = {}
    for pkg, meta in all_packages.items():
        url = meta.get("url", "")
        if url:
            by_url.setdefault(url, []).append(pkg)

    for url, pkgs in sorted(by_url.items()):
        if len(pkgs) > 1:
            warnings.append(
                f"url '{url}' is shared by packages: {', '.join(sorted(pkgs))}"
                " — verify each has independent auto_update.release_type"
            )

    return errors, warnings


def validate_gitmodules(root_path=ROOT) -> tuple[list[str], list[str]]:
    """Validate .gitmodules conventions.

    Checks:
    - Submodule paths start with "submodules/"
    - URLs use https://

    Args:
        root_path: Path to repository root

    Returns:
        Tuple of (errors, warnings) as lists of strings
    """
    errors: list[str] = []
    warnings: list[str] = []
    gitmodules_path = GITMODULES
    if not gitmodules_path.exists():
        return errors, warnings

    modules = parse_gitmodules(gitmodules_path)
    for mod in modules:
        path = mod.get("path", "")
        url = mod.get("url", "")
        if path and not path.startswith("submodules/"):
            errors.append(
                f".gitmodules: submodule '{mod['name']}' path '{path}' does not start with submodules/"
            )
        if url and not url.startswith("https://"):
            errors.append(
                f".gitmodules: submodule '{mod['name']}' URL '{url}' is not https://"
            )

    return errors, warnings
