"""Version string utilities."""

import re

# Strict semver: v?MAJOR.MINOR.PATCH with no extra suffixes
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# Loose version-like tag: v?N(.N)*  optionally followed by a pre-release suffix
# (-rc1, -beta, .rc2, etc). Looser than SEMVER_RE on purpose -- latest-tag exists
# specifically for upstreams (e.g. mpvpaper) that don't tag strict three-component
# semver, so any run of dot-separated numbers qualifies.
TAG_RE = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-.]([0-9A-Za-z.]+))?$")
_PRERELEASE_PART_RE = re.compile(r"(\d+)|([A-Za-z]+)")

# The complete set of release_type values scripts/update-versions.py and the
# validators understand. Single source of truth -- see docs/bugs.md BUG-0014:
# a release_type outside this set used to match no dispatch branch and fall
# through to the default (semver-or-commit) path silently instead of erroring.
RELEASE_TYPES = frozenset(
    {
        "latest-version",
        "latest-tag",
        "latest-commit",
        "pinned-version",
        "pinned-commit",
        "pinned-tag",
    }
)

# Types that pin the *checkout*, not just the version string. Exact membership
# on purpose, never startswith("pinned-"): an unknown/misspelled type must
# behave identically here and in the version-resolution loop below, which
# falls through to the default path. See docs/bugs.md BUG-0014 (mpvpaper's
# `latest-tag`); docs/packaging.md holds the canonical release_type table.
PINNED_RELEASE_TYPES = frozenset({"pinned-version", "pinned-commit", "pinned-tag"})

# release_types whose resolved *version string* is itself a commit descriptor
# (`1.2.3^20240101gitabc1234`), written via pkg_to_commit_info rather than
# pkg_to_latest. latest-tag is excluded: it resolves a real tag through
# pkg_to_latest, same as latest-version.
COMMIT_VERSION_RELEASE_TYPES = frozenset({"latest-commit", "pinned-tag"})

# release_types whose build actually downloads a specific commit's tarball (the
# archive URL is templated as `%{url}/archive/%{commit}.tar.gz`, with
# source.commit.full written by update-versions.py). Every other release_type
# builds from a fixed version/tag tarball URL that has no commit in it at all.
# See docs/bugs.md BUG-0033, BUG-0034.
COMMIT_TRACKED_RELEASE_TYPES = frozenset({"latest-commit", "pinned-commit"})


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


def _prerelease_key(suffix: str | None) -> tuple:
    """Sort key for a pre-release suffix so alpha < beta < rc and rc1 < rc2.

    Splits into alternating alpha/numeric runs; each numeric run sorts as
    (0, int) and each alpha run as (1, str), so e.g. "rc1" -> ((1,"rc"),(0,1)).
    """
    if suffix is None:
        return ()
    parts: list[tuple[int, int] | tuple[int, str]] = []
    for m in _PRERELEASE_PART_RE.finditer(suffix):
        if m.group(1) is not None:
            parts.append((0, int(m.group(1))))
        else:
            parts.append((1, m.group(2)))
    return tuple(parts)


def latest_tag(tags: list[str]) -> str | None:
    """Return the highest version-like tag, or None if no tag matches TAG_RE.

    Unlike latest_semver, accepts any number of dot-separated numeric
    components (mpvpaper tags as "1.9", not "1.9.0") and an optional
    pre-release suffix, which sorts below the same numeric tag without one
    (e.g. "2.0.0" beats "2.0.0-rc1", but "2.0.0-rc1" beats "1.9"). The
    returned tag is verbatim (including any "v" prefix) -- callers that need
    an RPM-safe version string should pass it through rpm_version_from_tag().
    """
    best_tag = None
    best_key: tuple | None = None
    for tag in tags:
        m = TAG_RE.match(tag)
        if not m:
            continue
        numeric = tuple(int(part) for part in m.group(1).split("."))
        is_release = m.group(2) is None
        key = (
            (numeric, 1, ())
            if is_release
            else (numeric, 0, _prerelease_key(m.group(2)))
        )
        if best_key is None or key > best_key:
            best_key = key
            best_tag = tag
    return best_tag


def rpm_version_from_tag(tag: str) -> str:
    """Convert a version-like tag into an RPM-legal Version string.

    Strips a leading "v" (matching latest_semver's .lstrip("v") convention)
    and replaces a "-" pre-release separator with "~" ("-" is illegal in an
    RPM Version). A plain numeric tag like "1.9" is returned unchanged, so
    for every package selecting one today this is a no-op. When a
    pre-release tag does win, the result ("2.0.0~rc1") no longer matches the
    upstream tag string byte-for-byte -- a source.archives entry templated
    on %{version} would need the tag itself, not this value; callers should
    warn when the two diverge.
    """
    stripped = tag.lstrip("v")
    return stripped.replace("-", "~", 1)


def nvr(version: str, release: int | str, fedora_version: str) -> str:
    """Format a version-release-dist string."""
    dist = "rawhide" if fedora_version == "rawhide" else f"fc{fedora_version}"
    return f"{version}-{release}.{dist}"


def clean_version(raw: str) -> str:
    """Strip -<release>.fcXX suffix (e.g., -1.fc43, -5.fc44), keep bare version."""
    return raw.split("-")[0] if raw else ""
