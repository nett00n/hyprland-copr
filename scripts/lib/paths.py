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

# The build matrix is fedora+x86_64-only today; see docs/todo.md "Build matrix"
# for what else needs to change before that's not true.
DISTRO = "fedora"
ARCH = "x86_64"


def get_package_log_dir(pkg_name: str) -> Path:
    """Return the build log directory for a package."""
    return BUILD_LOG_DIR / pkg_name


def mock_chroot(fedora_version: str) -> str:
    """Return the mock chroot name for the given Fedora version."""
    if fedora_version == "rawhide":
        return "fedora-rawhide-x86_64"
    return f"fedora-{fedora_version}-x86_64"


def resolve_target(fedora_version: str, mock_chroot_override: str = "") -> str:
    """Return the build_db `target` key: MOCK_CHROOT override if set, else derived
    from fedora_version. This is also the actual mock chroot name passed to `mock -r`.
    """
    return mock_chroot_override or mock_chroot(fedora_version)


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
