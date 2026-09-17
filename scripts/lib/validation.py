"""Package validation utilities.

Validates package.yaml entries, group membership, and .gitmodules conventions.
"""

import re
from pathlib import Path

from lib.detection import BUILD_SYSTEM_MARKERS, matches_build_system
from lib.gitmodules import get_tag_commit, get_tag_info, parse_gitmodules
from lib.paths import ROOT
from lib.subprocess_utils import run_git
from lib.vendor import needs_vendoring
from lib.version import COMMIT_TRACKED_RELEASE_TYPES, RELEASE_TYPES
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
VALID_FEDORA_OVERRIDE_KEYS = {"skip"}

# #BUG-0097: dotted-path -> expected scalar type for packages.yaml fields, derived
# from packages.yaml.example. Only fields actually present are checked (absence is
# REQUIRED_FIELDS' job); `bool` is checked exactly (never accepted where `int` is
# expected -- Python's bool is an int subclass) and vice versa. Nested `dict`/list
# *contents* (e.g. fedora: override keys) are validated by their own dedicated
# checks elsewhere in this module.
FIELD_TYPES: dict[str, type] = {
    "version": str,
    "release": int,
    "license": str,
    "summary": str,
    "description": str,
    "url": str,
    "source_dir": str,
    "source_name": str,
    "auto_update.release_type": str,
    "build.system": str,
    "build.go_subdir": str,
    "build.save_files": str,
    "build.no_lto": bool,
    "build.prep": list,
    "build.commands": list,
    "build.install": list,
    "build.configure_flags": list,
    "build.cargo_update": list,
    "build_requires": list,
    "depends_on": list,
    "requires": list,
    "recommends": list,
    "files": list,
    "devel.files": list,
    "devel.requires": list,
    "rpm.buildarch": str,
    "rpm.no_debug_package": bool,
    "source.archives": list,
    "source.bundled_deps": list,
    "source.name": str,
    "source.source_dir": str,
    "source.commit.full": str,
    "source.commit.date": str,
}

_MISSING = object()


def _get_dotted(meta: dict, path: str) -> object:
    """Walk a dotted path through nested dicts, returning _MISSING if absent."""
    obj: object = meta
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return _MISSING
        obj = obj[part]
    return obj


def validate_field_types(name: str, meta: dict) -> tuple[list[str], list[str]]:
    """#BUG-0097: reject packages.yaml scalars whose type doesn't match FIELD_TYPES.

    Presence is REQUIRED_FIELDS' job; this only checks fields that are present.
    A YAML scalar like `version: 1.9` (a float) or `release: true` (a bool) used
    to pass validation silently -- see docs/CHANGELOG.md 2026-08-28.

    Args:
        name: Package name (unused, kept for signature symmetry with validate_package)
        meta: Package metadata dict

    Returns:
        Tuple of (errors, warnings) as lists of strings -- always empty warnings
    """
    errors: list[str] = []
    warnings: list[str] = []

    for path, expected in FIELD_TYPES.items():
        value = _get_dotted(meta, path)
        if value is _MISSING or value is None:
            continue
        if expected is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif expected is bool:
            valid = isinstance(value, bool)
        else:
            valid = isinstance(value, expected)
        if not valid:
            errors.append(
                f"{path}: expected {expected.__name__}, got "
                f"{type(value).__name__} ({value!r})"
            )

    return errors, warnings


_SOURCE_INDEX_RE = re.compile(r"%\{SOURCE(\d+)\}")


def validate_vendoring(name: str, meta: dict) -> tuple[list[str], list[str]]:
    """#BUG-0089: cross-validate the vendoring trigger against its declared source.

    Three sources of truth exist for a package's Go/Rust vendor tarball and none
    were compared: `build_requires` containing golang/cargo (lib.vendor.needs_vendoring,
    which drives whether stage-vendor actually runs), a `*-vendor.tar.gz` entry in
    `source.archives` (what the generated spec's Source1+ line points at), and a
    hand-written `build.prep`'s `%{SOURCEn}` reference (auto-injected by
    stage-spec.py when absent, but never checked against the archives list when
    present, e.g. aylurs-gtk-shell's `pushd cli` variant).

    Args:
        name: Package name (unused, kept for signature symmetry with validate_package)
        meta: Package metadata dict

    Returns:
        Tuple of (errors, warnings) as lists of strings -- always empty warnings
    """
    errors: list[str] = []
    warnings: list[str] = []

    archives = (meta.get("source") or {}).get("archives") or []
    has_vendor_archive = any(
        isinstance(a, str) and a.endswith("-vendor.tar.gz") for a in archives
    )
    triggers_vendor = needs_vendoring(meta)

    if triggers_vendor and not has_vendor_archive:
        errors.append(
            "build_requires triggers vendoring (golang/cargo) but source.archives "
            "has no '*-vendor.tar.gz' entry -- the vendor stage's tarball is "
            "referenced by nothing"
        )
    if has_vendor_archive and not triggers_vendor:
        errors.append(
            "source.archives declares a vendor tarball but build_requires has no "
            "golang/cargo -- the vendor stage never runs, so it's never produced"
        )

    prep = (meta.get("build") or {}).get("prep") or []
    for cmd in prep:
        if not isinstance(cmd, str):
            continue
        for m in _SOURCE_INDEX_RE.finditer(cmd):
            idx = int(m.group(1))
            if idx >= len(archives):
                errors.append(
                    f"build.prep references %{{SOURCE{idx}}} but source.archives "
                    f"has only {len(archives)} entr{'y' if len(archives) == 1 else 'ies'}"
                )

    return errors, warnings


def validate_dependency_drift(
    all_packages: dict, root_path: Path = ROOT
) -> tuple[list[str], list[str]]:
    """#BUG-0056: warn when a commit-tracked package outruns a tag-pinned dependency.

    Offline and degrading by design: reads only local submodule git state via the
    existing lib.gitmodules.get_tag_commit(), and skips silently -- no warning --
    whenever a submodule isn't initialized or its dependency's tag isn't fetched
    locally, so CI and fresh clones stay green. This is the drift class that broke
    `hyprland-plugins` (pinned-commit, tracking Hyprland's unreleased main API)
    against `Hyprland` (pinned to v0.56.2) across all three chroots (runs 76-78)
    before mock caught it -- nothing flagged it beforehand.

    Warning-level, not error: a commit-tracked package being ahead of a pinned
    sibling is common and often correct (that's what `latest-commit` is for); the
    point is making the drift visible, not blocking on it.

    Args:
        all_packages: Dict of all packages
        root_path: Path to repository root (submodules live under
            `root_path / "submodules"`, resolved via .gitmodules)

    Returns:
        Tuple of (errors, warnings) as lists of strings -- always empty errors
    """
    errors: list[str] = []
    warnings: list[str] = []

    gitmodules_path = root_path / ".gitmodules"
    if not gitmodules_path.exists():
        return errors, warnings

    modules = parse_gitmodules(gitmodules_path)
    url_to_path = {mod["url"]: mod.get("path") for mod in modules}
    pkg_by_lower = {k.lower(): k for k in all_packages}

    for name, meta in sorted(all_packages.items()):
        release_type = (meta.get("auto_update") or {}).get("release_type")
        if release_type not in COMMIT_TRACKED_RELEASE_TYPES:
            continue
        commit = meta.get("source", {}).get("commit")
        a_date = commit.get("date") if isinstance(commit, dict) else None
        if not a_date:
            continue

        for dep in meta.get("depends_on") or []:
            dep_key = pkg_by_lower.get(str(dep).lower())
            if dep_key is None:
                continue
            dep_meta = all_packages[dep_key]
            dep_release_type = (dep_meta.get("auto_update") or {}).get("release_type")
            if dep_release_type in COMMIT_TRACKED_RELEASE_TYPES:
                continue  # only compare against tag/version-pinned siblings

            dep_path = url_to_path.get(dep_meta.get("url", ""))
            if not dep_path:
                continue
            repo = root_path / dep_path
            if not repo.is_dir():
                continue  # submodule not initialized

            dep_version = str(dep_meta.get("version", ""))
            if not dep_version:
                continue
            tag_info = get_tag_commit(repo, f"v{dep_version}")
            if tag_info is None:
                continue  # tag not resolvable locally
            _, _, dep_date, _ = tag_info

            if a_date > dep_date:
                warnings.append(
                    f"'{name}' source.commit.date ({a_date}) is newer than "
                    f"depends_on '{dep_key}' pinned tag v{dep_version} ({dep_date}) "
                    "-- possible API drift ahead of a pinned dependency (the class "
                    "of bug that broke hyprland-plugins against Hyprland, "
                    "runs 76-78)"
                )

    return errors, warnings


def validate_build_system_drift(
    all_packages: dict, root_path: Path = ROOT
) -> tuple[list[str], list[str]]:
    """#COPR-0010, #BUG-0105: warn when a submodule's tagged tree no longer ships the
    build_system marker packages.yaml declares.

    Offline and degrading by design, same contract as validate_dependency_drift():
    reads only local submodule git state (a tag's committed tree via `git ls-tree`,
    never the checked-out working tree, so a stale checkout can't produce a false
    verdict) and skips silently -- no warning, no error -- whenever a submodule isn't
    initialized or the version tag isn't resolvable locally. This is the drift class
    that broke `hyprland-protocols` 0.7.1 (upstream's `meson -> cmake` commit dropped
    meson.build; packages.yaml still said `build.system: meson`) across all three
    chroots (runs 136-138) before mock caught it -- nothing flagged it beforehand.

    Warning-level, not error: a false positive here (e.g. a repo that ships both
    meson.build and CMakeLists.txt) must never block `make update-daily`'s nightly
    Copr publish.

    Args:
        all_packages: Dict of all packages
        root_path: Path to repository root (submodules live under
            `root_path / "submodules"`, resolved via .gitmodules)

    Returns:
        Tuple of (errors, warnings) as lists of strings -- always empty errors
    """
    errors: list[str] = []
    warnings: list[str] = []

    gitmodules_path = root_path / ".gitmodules"
    if not gitmodules_path.exists():
        return errors, warnings

    modules = parse_gitmodules(gitmodules_path)
    url_to_path = {mod["url"]: mod.get("path") for mod in modules}

    for name, meta in sorted(all_packages.items()):
        declared = (meta.get("build") or {}).get("system")
        if declared not in BUILD_SYSTEM_MARKERS:
            continue  # unknown/unset system, or one with no marker to check

        pkg_path = url_to_path.get(meta.get("url", ""))
        if not pkg_path:
            continue
        repo = root_path / pkg_path
        if not repo.is_dir():
            continue  # submodule not initialized

        commit = meta.get("source", {}).get("commit")
        ref: str | None = None
        if isinstance(commit, dict) and commit.get("hash"):
            ref = commit["hash"]
        else:
            version = str(meta.get("version", ""))
            if version:
                tag_info = get_tag_info(repo, version)
                ref = tag_info["tag"] if tag_info else None
        if not ref:
            continue  # tag/commit not resolvable locally

        tree = run_git("ls-tree", "--name-only", ref, cwd=repo, timeout=10)
        if tree.returncode != 0:
            continue  # ref not resolvable locally
        entries = set(tree.stdout.split())
        if matches_build_system(declared, entries):
            continue

        detected = next(
            (
                system
                for system in BUILD_SYSTEM_MARKERS
                if system != declared and matches_build_system(system, entries)
            ),
            None,
        )
        detail = f" -- looks like '{detected}' now" if detected else ""
        warnings.append(
            f"'{name}' declares build.system: {declared} but {ref}'s tree doesn't "
            f"match it{detail} -- upstream may have switched build systems (fix "
            "build.system in packages.yaml)"
        )

    return errors, warnings


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
    - packages.yaml scalar types match FIELD_TYPES (#BUG-0097)
    - vendoring trigger cross-checked against declared source (#BUG-0089)

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

    type_errors, type_warnings = validate_field_types(name, meta)
    errors.extend(type_errors)
    warnings.extend(type_warnings)

    vendor_errors, vendor_warnings = validate_vendoring(name, meta)
    errors.extend(vendor_errors)
    warnings.extend(vendor_warnings)

    # source.archives required
    if not meta.get("source", {}).get("archives"):
        errors.append("missing required field: source.archives")
    else:
        from lib.source_lock import load_lock, remote_sources
        from lib.spec_utils import process_archive_urls

        pkg_lock = load_lock().get(name, {})
        missing = [
            filename
            for filename, _url in remote_sources(name, meta)
            if filename not in pkg_lock
        ]
        if missing:
            warnings.append(
                f"no sources.lock.yaml entry for: {', '.join(missing)} -- "
                f"run: make refresh-checksums PACKAGE={name} (see docs/CHANGELOG.md BUG-0025)"
            )

        # archives[0] must resolve to a downloadable URL -- later entries may
        # be bare filenames (that's how vendor tarballs are referenced), but
        # a bare entry 0 silently defeats spectool (see docs/BUGS.md BUG-0026).
        source = meta.get("source", {}) or {}
        processed = process_archive_urls(
            source.get("archives", []),
            meta.get("url", ""),
            name,
            source.get("commit") if isinstance(source.get("commit"), dict) else None,
            str(meta.get("version", "")),
        )
        first = str(processed[0]).strip('"') if processed else ""
        if not first.startswith("https://"):
            errors.append(
                f"source.archives[0] must be a downloadable URL (https://...), got: {first!r}"
            )

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

    # auto_update.release_type validity -- an unrecognized type used to match
    # no dispatch branch in update-versions.py and silently fall through to
    # the default (semver-or-commit) resolution instead of erroring here (see
    # docs/BUGS.md BUG-0014, e.g. mpvpaper's `latest-tag` before it was added
    # as a real type).
    release_type = (meta.get("auto_update") or {}).get("release_type")
    if release_type and release_type not in RELEASE_TYPES:
        errors.append(
            f"unknown auto_update.release_type '{release_type}' "
            f"(valid: {', '.join(sorted(RELEASE_TYPES))})"
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
            if dep.lower() == name.lower():
                errors.append(
                    f"depends_on: self-dependency detected (remove '{dep}' "
                    "from depends_on)"
                )
            elif dep.lower() not in pkg_by_lower:
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
        if (
            base
            and base in pkg_by_lower
            and pkg_by_lower[base] != name
            and base not in depends_on_lower
        ):
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
                    f"fedora.{ver_key}: unknown override key(s) "
                    f"{', '.join(sorted(unknown_keys))} (only 'skip' is supported -- write a "
                    f"per-version difference as a literal '%if 0%{{?fedora}} == "
                    f"{ver_key} ... %endif' conditional in build.prep/commands/install "
                    "instead)"
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


def validate_submodule_url_resolution(
    all_packages: dict, modules: list[dict]
) -> tuple[list[str], list[str]]:
    """Warn when a package's url won't resolve to any .gitmodules submodule.

    update-versions.py resolves each package's submodule via an EXACT string
    match against .gitmodules urls (`url_to_module = {mod["url"]: mod}`), not
    a normalized one. A mismatch -- commonly a stray or missing trailing
    `.git` -- means the package is silently skipped every run: no error, no
    warning at update time, auto_update simply never fires again. See
    docs/BUGS.md BUG-0013: two packages went weeks with no update before this
    was noticed by hand. (Distinct from validate_no_duplicate_urls, which
    catches two *packages* colliding on the same url -- this catches one
    package's url failing to match its own submodule at all.)

    Args:
        all_packages: Dict of all packages
        modules: Parsed .gitmodules entries (see lib.gitmodules.parse_gitmodules)

    Returns:
        Tuple of (errors, warnings) as lists of strings -- always empty errors
    """
    errors: list[str] = []
    warnings: list[str] = []

    gitmodules_urls = {mod["url"] for mod in modules}

    for pkg, meta in sorted(all_packages.items()):
        url = meta.get("url", "")
        if url and url not in gitmodules_urls:
            warnings.append(
                f"package '{pkg}' url '{url}' does not match any .gitmodules"
                " submodule url -- update-versions.py will silently skip its"
                " auto_update every run (check for a .git-suffix mismatch)"
            )

    return errors, warnings


def validate_gitmodules(root_path: Path = ROOT) -> tuple[list[str], list[str]]:
    """Validate .gitmodules conventions.

    Checks:
    - Submodule paths start with "submodules/"
    - URLs use https://
    - Every submodule has `ignore = dirty` set (formerly only checked by
      scripts/validate-packages.py, one of the two divergences behind
      docs/BUGS.md formerly BUG-0012 -- a submodule missing it shows as
      locally "dirty" in `git status` on every commit its upstream makes,
      even with nothing checked out differently)

    Args:
        root_path: Path to repository root (the .gitmodules file is read from
            `root_path / ".gitmodules"`)

    Returns:
        Tuple of (errors, warnings) as lists of strings
    """
    errors: list[str] = []
    warnings: list[str] = []
    gitmodules_path = root_path / ".gitmodules"
    if not gitmodules_path.exists():
        return errors, warnings

    modules = parse_gitmodules(gitmodules_path)
    for mod in modules:
        path = mod.get("path", "")
        url = mod.get("url", "")
        ignore = mod.get("ignore")
        if path and not path.startswith("submodules/"):
            errors.append(
                f".gitmodules: submodule '{mod['name']}' path '{path}' does not start with submodules/"
            )
        if url and not url.startswith("https://"):
            errors.append(
                f".gitmodules: submodule '{mod['name']}' URL '{url}' is not https://"
            )
        if ignore is None:
            errors.append(
                f".gitmodules: submodule '{mod['name']}' missing 'ignore = dirty'"
            )
        elif ignore != "dirty":
            errors.append(
                f".gitmodules: submodule '{mod['name']}' ignore={ignore}, should be 'ignore = dirty'"
            )

    return errors, warnings


_ENV_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=")


def validate_env_file(root_path: Path = ROOT) -> list[str]:
    """#BUG-0052: warn when `.env` assigns the same key more than once.

    `.env` is gitignored and read by Make via `-include .env` -- Make keeps
    only the last assignment of a repeated key, silently overriding whatever
    an earlier line said. A `make full-cycle` reading a `.env` with
    `SKIP_COPR` assigned twice submits to Copr or not depending purely on
    which line comes last, with no warning either way.

    Args:
        root_path: Path to repository root (`.env` is read from
            `root_path / ".env"`)

    Returns:
        List of warning strings, one per repeated key, each naming the key
        and every line it was assigned on (1-indexed). Empty (never errors)
        when `.env` is absent -- CI and fresh clones have none.
    """
    warnings: list[str] = []
    env_path = root_path / ".env"
    if not env_path.exists():
        return warnings

    lines_by_key: dict[str, list[int]] = {}
    for lineno, line in enumerate(env_path.read_text().splitlines(), start=1):
        match = _ENV_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        lines_by_key.setdefault(match.group(1), []).append(lineno)

    for key, linenos in lines_by_key.items():
        if len(linenos) > 1:
            line_list = ", ".join(str(n) for n in linenos)
            warnings.append(
                f".env: '{key}' assigned {len(linenos)} times (lines {line_list})"
                " -- Make keeps only the last one"
            )

    return warnings


_TRACKER_ID_RE = re.compile(r"^- #(BUG|TODO)-(\d+)\b")
_TRACKER_FILES = {"BUGS.md": "BUG", "TODO.md": "TODO"}


def validate_tracker_ids(root_path: Path = ROOT) -> list[str]:
    """#BUG-0073: error when a `#BUG-`/`#TODO-` ID is declared twice, or misfiled.

    Greps `docs/BUGS.md`/`docs/TODO.md` for `^- #(BUG|TODO)-NNNN` declarations --
    the exact grep the 2026-08-18 grooming pass used by hand after finding two
    TODO entries silently reallocated after deletion, and a stale `## Next`
    section duplicating BUG-0018. Also flags an ID filed under the wrong file's
    prefix (a `#TODO-` line in BUGS.md or vice versa).

    Args:
        root_path: Path to repository root (files are read from
            `root_path / "docs" / "BUGS.md"` and `.../TODO.md`)

    Returns:
        List of error strings, one per duplicate or misfiled ID. Empty when
        both files are absent or internally consistent.
    """
    errors: list[str] = []

    for filename, expected_prefix in _TRACKER_FILES.items():
        path = root_path / "docs" / filename
        if not path.exists():
            continue

        lines_by_id: dict[str, list[int]] = {}
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            match = _TRACKER_ID_RE.match(line)
            if not match:
                continue
            prefix, number = match.group(1), match.group(2)
            tracker_id = f"{prefix}-{number}"
            if prefix != expected_prefix:
                errors.append(
                    f"docs/{filename}:{lineno}: '#{tracker_id}' has the wrong "
                    f"prefix for this file (expected #{expected_prefix}-NNNN)"
                )
                continue
            lines_by_id.setdefault(tracker_id, []).append(lineno)

        for tracker_id, linenos in lines_by_id.items():
            if len(linenos) > 1:
                line_list = ", ".join(str(n) for n in linenos)
                errors.append(
                    f"docs/{filename}: '#{tracker_id}' declared {len(linenos)} "
                    f"times (lines {line_list})"
                )

    return errors
