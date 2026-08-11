"""Preflight checks for the mock build stage.

`stage-mock.py`'s `run_for_package()` calls `check_buildroot_repo()` right
before it would spawn mock, so a local dependency that's missing from
`local-repo/<target>/` (or, structurally impossible after the per-chroot
layout but checked anyway as a tripwire, present with the wrong Fedora dist
tag) fails in seconds with an actionable message -- instead of the ~5-minute
round trip through mock bootstrapping a buildroot only for dnf5 to fail
resolving the transaction (see docs/CHANGELOG.md 2026-08-11, and the
"nothing provides libdisplay-info.so.2()(64bit)" failure that prompted this).

`make stage-mock PACKAGE=x` -- unlike `full-cycle.py` -- does not expand `x`'s
local dependencies and build them first, so `x`'s deps may simply never have
been built for the target chroot at all. This module reports that; it
deliberately does not auto-build anything.
"""

import re
import subprocess
from pathlib import Path

from lib import build_db
from lib.deps import build_dep_graph, effective_deps, transitive_deps
from lib.yaml_utils import apply_os_overrides

# fedora-44-x86_64 -> "44"; fedora-rawhide-x86_64 has no leading digits and
# doesn't match, which is intentional (see target_dist_tag).
_TARGET_VERSION_RE = re.compile(r"^fedora-(\d+)-")

# fc44, el9, etc. -- the dist-tag component of an RPM release string.
_DIST_TAG_RE = re.compile(r"(fc\d+|el\d+)")


def target_dist_tag(target: str) -> str | None:
    """Return the dist tag a chroot's own packages carry, e.g.
    "fedora-44-x86_64" -> "fc44".

    Returns None for rawhide (and anything else not matching the
    fedora-<N>-<arch> shape): rawhide's dist tag floats release to release,
    so a foreign-dist check would false-positive on a perfectly normal
    rawhide repo. Foreign-dist checking is skipped entirely in that case.
    """
    m = _TARGET_VERSION_RE.match(target)
    return f"fc{m.group(1)}" if m else None


def rpm_dist_tag(path: Path) -> str | None:
    """Return an RPM's dist tag.

    Tries the filename first (cheap, no subprocess -- NVRA filenames almost
    always carry it), falling back to `rpm -qp --qf %{RELEASE}` for the rare
    filename that doesn't. Returns None if neither yields a recognizable tag.
    """
    m = _DIST_TAG_RE.search(path.name)
    if m:
        return m.group(1)
    result = subprocess.run(
        ["rpm", "-qp", "--queryformat", "%{RELEASE}", str(path)],
        capture_output=True,
        text=True,
    )
    m = _DIST_TAG_RE.search(result.stdout)
    return m.group(1) if m else None


def format_local_repo_remedy(names: list[str], fedora_version: str) -> str:
    """One-sentence remedy for a missing/stale local-repo dependency.

    Shared between this preflight and the post-hoc `_analyze_mock_root_log`
    detector in `lib/log_analysis.py`, so a build-time failure and a
    log-analysis-time diagnosis of the same underlying problem never drift
    into different wording.
    """
    rebuild_cmds = "; ".join(
        f"`make stage-mock PACKAGE={n} FEDORA_VERSION={fedora_version}`" for n in names
    )
    return (
        f"local-repo build of {'/'.join(names)} is stale/incompatible with the "
        "current buildroot (commonly: built against a different chroot's library "
        f"soname); rebuild it for this chroot first: {rebuild_cmds}; if local-repo "
        "still doesn't pick up the rebuild, clear the stale cache: "
        "`make clean-mock-cache FEDORA_VERSION=<ver>` or "
        "`make clean-localrepo FEDORA_VERSION=<ver>`"
    )


def _rpm_present(repo_dir: Path, dep: str) -> bool:
    """True if repo_dir has a non-.src.rpm whose filename starts with dep's
    name (case-insensitive -- packages.yaml keys are mixed case, e.g.
    "Hyprland", while the RPM on disk is lowercase)."""
    if not repo_dir.exists():
        return False
    pattern = re.compile(rf"^{re.escape(dep)}-[0-9]", re.IGNORECASE)
    return any(
        pattern.match(rpm.name) and not rpm.name.endswith(".src.rpm")
        for rpm in repo_dir.glob("*.rpm")
    )


def check_buildroot_repo(
    pkg: str,
    meta: dict,
    all_packages: dict,
    target: str,
    fedora_version: str,
    repo_dir: Path,
) -> tuple[list[str], list[str]]:
    """Check whether `repo_dir` is ready to serve `pkg`'s local build deps
    into `target`'s buildroot. Returns (errors, warnings); errors should
    block the mock stage, warnings should just be logged.
    """
    errors: list[str] = []
    warnings: list[str] = []

    repomd = repo_dir / "repodata" / "repomd.xml"
    if not repo_dir.exists() or not repomd.exists():
        warnings.append(
            f"local-repo/{target} has no repodata yet -- fresh chroot, or no local "
            "deps have been built for it yet; stage-mock regenerates it before "
            "building, so this is expected for the first build of a new target"
        )

    dist_tag = target_dist_tag(target)
    if dist_tag and repo_dir.exists():
        foreign = sorted(
            rpm.name
            for rpm in repo_dir.glob("*.rpm")
            if not rpm.name.endswith(".src.rpm")
            and rpm_dist_tag(rpm) not in (None, dist_tag)
        )
        if foreign:
            errors.append(
                f"local-repo/{target} contains RPM(s) built for a different Fedora "
                f"version: {', '.join(foreign)} -- this should be structurally "
                "impossible under the per-chroot layout, so something hand-copied "
                "them there; clear it with "
                f"`make clean-localrepo FEDORA_VERSION={fedora_version}`"
            )

    graph = build_dep_graph(all_packages)
    direct = effective_deps(pkg, meta, all_packages)
    is_explicit_pkg = meta.get("depends_on") is not None
    needed = transitive_deps(pkg, graph)

    for dep in sorted(needed):
        dep_meta = all_packages.get(dep)
        if dep_meta is None:
            continue
        dep_meta = apply_os_overrides(dep_meta, fedora_version)
        if dep_meta.get("_skip"):
            continue
        dep_stage = build_db.get_stage(dep, "mock", target)
        if dep_stage and dep_stage.get("state") == "skipped":
            continue
        if _rpm_present(repo_dir, dep):
            continue

        msg = (
            f'local dependency "{dep}" not found in local-repo/{target} -- '
            + format_local_repo_remedy([dep], fedora_version)
        )
        # Explicit `depends_on` (first hop, or anything only reachable through
        # another package's own edge) is authoritative -> error. A first-hop
        # dep inferred from the `-devel` build_requires fallback is a
        # heuristic and must not block a build on a false positive -> warning.
        if dep not in direct or is_explicit_pkg:
            errors.append(msg)
        else:
            warnings.append(msg)

    return errors, warnings
