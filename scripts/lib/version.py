"""Version string utilities."""

import re

# Strict semver: v?MAJOR.MINOR.PATCH with no extra suffixes
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def latest_semver(tags: list[str]) -> str | None:
    """Return the tag string with the highest semver, or None if no semver tags found."""
    best_tag = None
    best_tuple = (-1, -1, -1)
    for tag in tags:
        m = SEMVER_RE.match(tag)
        if not m:
            continue
        t = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if t > best_tuple:
            best_tuple = t
            best_tag = tag
    return best_tag


def nvr(version: str, release: int | str, fedora_version: str) -> str:
    """Format a version-release-dist string."""
    dist = "rawhide" if fedora_version == "rawhide" else f"fc{fedora_version}"
    return f"{version}-{release}.{dist}"


def clean_version(raw: str) -> str:
    """Strip -%autorelease.fcXX or -1.fcXX suffix, keep bare version number."""
    return raw.split("-")[0] if raw else ""
