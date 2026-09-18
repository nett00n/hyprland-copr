"""Canonical path constants for the hyprland-copr repository."""

import re
from pathlib import Path

# scripts/lib/ -> scripts/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGES_YAML = ROOT / "packages.yaml"
REPO_YAML = ROOT / "repo.yaml"
GROUPS_YAML = ROOT / "groups.yaml"
SOURCES_LOCK = ROOT / "sources.lock.yaml"
GITMODULES = ROOT / ".gitmodules"
LOG_DIR = ROOT / "logs"
BUILD_LOG_DIR = LOG_DIR / "build"
LOCAL_REPO_ROOT = ROOT / "local-repo"
TEMPLATE_DIR = ROOT / "templates"
GITHUB_RELEASE_CACHE = ROOT / "cache" / "github-releases.json"
BUILD_DB = ROOT / "build-report.db"
SOURCES_DIR = Path.home() / "rpmbuild" / "SOURCES"

# Content-addressed vendor tarball store (lib/vendor_store.py). Distro/arch-independent
# by construction -- unlike SOURCES_DIR (one podman volume per FEDORA_VERSION), this
# lives on the repo's own /work mount, so one entry serves every target.
VENDOR_STORE_DIR = ROOT / ".cache" / "vendor"

# The build matrix is fedora+x86_64-only today; see docs/TODO.md "Build matrix"
# for what else needs to change before that's not true.
DISTRO = "fedora"
ARCH = "x86_64"

# The single container image (Containerfile) is pinned to this version -- the
# oldest SUPPORTED_FEDORA_VERSIONS, so a `BuildRequires: X-devel >= <ver>`
# resolved here (stage-spec.py's resolve_dep_versions()) stays satisfiable on
# every newer supported chroot too. `stage-copr.py` submits from this target's
# srpm row rather than the default FEDORA_VERSION's: with the rpmbuild volume
# shared across every target (docs/FRD.md COPR-0018) every target's row points
# at the same physical file today, but this is the one a matrix run is
# expected to always have populated.
CANONICAL_FEDORA_VERSION = "43"


def get_package_log_dir(pkg_name: str) -> Path:
    """Return the build log directory for a package."""
    return BUILD_LOG_DIR / pkg_name


def mock_chroot(fedora_version: str) -> str:
    """Return the mock chroot name for the given Fedora version."""
    return f"fedora-{fedora_version}-x86_64"


def resolve_target(fedora_version: str, mock_chroot_override: str = "") -> str:
    """Return the build_db `target` key: MOCK_CHROOT override if set, else derived
    from fedora_version. This is also the actual mock chroot name passed to `mock -r`.
    """
    return mock_chroot_override or mock_chroot(fedora_version)


# The container's bind-mount point for the repo root (Makefile WORKDIR_MOUNT:
# `$(PWD):/work:z`) -- every "repo"/"vendor-store" realm artifacts.path is
# recorded as an absolute path under here when written from inside the container.
_CONTAINER_ROOT = "/work"

# Realms whose artifacts live under the repo's own /work bind mount, and so have
# a real host-side path. `rpmbuild-volume` (a podman named volume) does not.
_HOST_RESOLVABLE_REALMS = frozenset({"repo", "vendor-store"})


def host_path(realm: str, path: str) -> Path | None:
    """#COPR-0015, #BUG-0062: resolve a recorded artifacts.path to a real path
    on the host, for tools (db-usage/db-prune/db-shell) that may run outside
    the container.

    Returns None for `rpmbuild-volume` -- its artifacts live in a podman named
    volume with no host filesystem path at all, so there's nothing to resolve;
    callers should report that explicitly rather than treat it as "missing".
    For `repo`/`vendor-store`, a path already recorded relative to the repo
    root (e.g. stage-mock.py's mock-log rows) is returned resolved against
    `ROOT` as-is; a `/work`-absolute path (the common case: RPMs, vendor
    tarballs) has that prefix swapped for `ROOT`; anything else (already
    host-resolved, e.g. this same call running outside a container) is
    returned unchanged.
    """
    if realm not in _HOST_RESOLVABLE_REALMS:
        return None
    p = Path(path)
    if not p.is_absolute():
        return ROOT / p
    try:
        return ROOT / p.relative_to(_CONTAINER_ROOT)
    except ValueError:
        return p


def local_repo(target: str) -> Path:
    """Return the per-chroot dnf repo dir mock resolves build deps against.

    Scoped by `target` (the same key build-report.db uses, e.g.
    "fedora-44-x86_64") so an RPM built for one Fedora version can never be
    served into a different version's buildroot -- see docs/CHANGELOG.md
    2026-08-11. There is deliberately no shared/unscoped LOCAL_REPO constant
    any more: a leftover alias is exactly how a caller would silently keep
    writing to an unscoped directory.
    """
    if not re.match(r"^[\w.-]+$", target):
        raise ValueError(f"Invalid target: {target}")
    return LOCAL_REPO_ROOT / target
