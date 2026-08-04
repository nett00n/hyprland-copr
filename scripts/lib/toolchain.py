"""Toolchain-skew detection (docs/todo.md TODO-0007).

Vendoring runs in the container against the container's own `go`/`cargo`;
the actual build runs in the mock chroot against whatever `golang`/`rust`
RPM the target Fedora release provides. A `go.mod` `toolchain` directive or
`Cargo.toml` `rust-version` pinned above the chroot's version vendors fine
but fails offline in the chroot, two stages later.

This checks the *chroot* side: what version the target Fedora release's repos
would install, queried via `dnf repoquery` (no chroot init required, and
vendoring already requires network). Best-effort -- a repoquery failure
(offline, package renamed, dnf unavailable) means "unknown", not "fail",
since this is a skew check, not the offline gate itself.
"""

import functools
import re
import subprocess
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore


def parse_go_toolchain_directive(go_mod: Path) -> str | None:
    """Return the minimum go version go.mod requires, preferring `toolchain`
    over the `go` directive, or None if go.mod has neither/doesn't exist.
    """
    if not go_mod.exists():
        return None
    text = go_mod.read_text(errors="replace")
    m = re.search(r"^toolchain\s+go(\S+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)", text, re.MULTILINE)
    if m:
        return m.group(1)
    return None


def parse_rust_version_directive(cargo_toml: Path) -> str | None:
    """Return Cargo.toml's [package] rust-version, or None if unset/missing."""
    if not cargo_toml.exists():
        return None
    try:
        data = tomllib.loads(cargo_toml.read_text(errors="replace"))
    except tomllib.TOMLDecodeError:
        return None
    return data.get("package", {}).get("rust-version")


def _version_tuple(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def compare_versions(a: str, b: str) -> int:
    """Return -1/0/1 comparing dotted version strings a and b, numeric parts only."""
    ta, tb = _version_tuple(a), _version_tuple(b)
    # Pad the shorter tuple so e.g. (1, 22) vs (1, 22, 3) compares as equal-prefix.
    length = max(len(ta), len(tb))
    ta += (0,) * (length - len(ta))
    tb += (0,) * (length - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


@functools.lru_cache(maxsize=None)
def chroot_package_version(rpm_name: str, fedora_version: str) -> str | None:
    """Best-effort: the version of `rpm_name` the target Fedora release's repos
    would install into the mock chroot, via `dnf repoquery`. None if it can't
    be determined (repoquery failure, package not found, dnf unavailable).
    """
    try:
        result = subprocess.run(
            [
                "dnf",
                "repoquery",
                "--quiet",
                "--latest-limit=1",
                f"--releasever={fedora_version}",
                "--qf=%{version}",
                rpm_name,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    version = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return version or None


def go_toolchain_skew(src_dir: Path, fedora_version: str) -> str | None:
    """Return an error message if go.mod's directive exceeds what the target
    Fedora release provides, else None (including when it can't be determined).
    """
    directive = parse_go_toolchain_directive(src_dir / "go.mod")
    if directive is None:
        return None
    chroot_version = chroot_package_version("golang", fedora_version)
    if chroot_version is None:
        return None
    if compare_versions(chroot_version, directive) < 0:
        return (
            f"go.mod requires toolchain go{directive}, but fedora-{fedora_version}'s "
            f"golang package is {chroot_version} -- the mock chroot build will fail offline"
        )
    return None


def rust_toolchain_skew(src_dir: Path, fedora_version: str) -> str | None:
    """Return an error message if Cargo.toml's rust-version exceeds what the
    target Fedora release provides, else None (including when it can't be
    determined).
    """
    directive = parse_rust_version_directive(src_dir / "Cargo.toml")
    if directive is None:
        return None
    chroot_version = chroot_package_version("rust", fedora_version)
    if chroot_version is None:
        return None
    if compare_versions(chroot_version, directive) < 0:
        return (
            f"Cargo.toml requires rust-version {directive}, but fedora-{fedora_version}'s "
            f"rust package is {chroot_version} -- the mock chroot build will fail offline"
        )
    return None
