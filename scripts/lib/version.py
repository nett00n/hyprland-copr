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
# validators understand. Single source of truth -- see docs/BUGS.md BUG-0014:
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
# falls through to the default path. See docs/BUGS.md BUG-0014 (mpvpaper's
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
# See docs/BUGS.md BUG-0033, BUG-0034.
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
    return f"{version}-{release}.fc{fedora_version}"


def clean_version(raw: str) -> str:
    """Strip -<release>.fcXX suffix (e.g., -1.fc43, -5.fc44), keep bare version."""
    return raw.split("-")[0] if raw else ""


VERSION_STAGE_PRECEDENCE = ("spec", "srpm", "mock", "copr")


def recorded_version(entries: list[dict | None], meta: dict) -> str:
    """Version to display for a package: first stage-recorded version, else declared.

    `entries` are stage_results rows (or None) in precedence order -- callers pass
    [spec, srpm, mock, copr] entries (see VERSION_STAGE_PRECEDENCE), the same precedence
    gen-report.py uses. Falls back to packages.yaml's declared `version` so pre-build
    tables (stage-show-plan) still show something useful, and to "-" if neither is
    available.
    """
    for entry in entries:
        raw = (entry or {}).get("version")
        if raw:
            return clean_version(str(raw))
    declared = meta.get("version")
    return clean_version(str(declared)) if declared else "-"


_VERCMP_SEGMENT_RE = re.compile(r"(\d+)|([A-Za-z]+)")


def rpmvercmp(a: str, b: str) -> int:
    """Compare two RPM Version (or Release) strings, rpm's own algorithm.

    Walks both strings left to right, skipping runs of characters that are
    neither alphanumeric nor `~`/`^` (rpm treats any such run as an
    equivalent separator), and compares one alternating alpha/numeric
    segment at a time: numeric segments compare as integers (so "05" ==
    "5") and always outrank an alpha segment at the same position; alpha
    segments compare byte-for-byte. `~` sorts below everything, including a
    missing segment (rpm's pre-release marker, e.g. "1.0~rc1" < "1.0"); `^`
    sorts above a missing segment (this repo's commit-snapshot suffix, e.g.
    "1.2.3^20240101gitabc1234" > "1.2.3" -- see COMMIT_VERSION_RELEASE_TYPES).
    Whichever string still has a segment left after the other is exhausted
    wins, unless that segment is itself `~` (loses) or `^` (wins).

    Returns negative/zero/positive like `cmp()`, for use as a `functools.
    cmp_to_key` comparator.
    """
    i = j = 0
    while i < len(a) or j < len(b):
        # Skip separator runs (anything not alphanumeric/~/^) on both sides.
        while i < len(a) and not (a[i].isalnum() or a[i] in "~^"):
            i += 1
        while j < len(b) and not (b[j].isalnum() or b[j] in "~^"):
            j += 1

        if i < len(a) and a[i] == "~":
            if j >= len(b) or b[j] != "~":
                return -1
            i += 1
            j += 1
            continue
        if j < len(b) and b[j] == "~":
            return 1

        if i < len(a) and a[i] == "^":
            if j >= len(b):
                return 1
            if b[j] != "^":
                return 1
            i += 1
            j += 1
            continue
        if j < len(b) and b[j] == "^":
            return -1

        if i >= len(a) or j >= len(b):
            break

        m_a = _VERCMP_SEGMENT_RE.match(a, i)
        m_b = _VERCMP_SEGMENT_RE.match(b, j)
        # a[i]/b[j] are known alnum here (separators/~/^ handled above), so
        # the digit-or-alpha regex always matches.
        assert m_a is not None
        assert m_b is not None
        seg_a = m_a.group(0)
        seg_b = m_b.group(0)
        a_numeric = m_a.group(1) is not None
        b_numeric = m_b.group(1) is not None

        if a_numeric != b_numeric:
            return 1 if a_numeric else -1
        if a_numeric:
            na, nb = int(seg_a), int(seg_b)
            if na != nb:
                return -1 if na < nb else 1
        elif seg_a != seg_b:
            return -1 if seg_a < seg_b else 1

        i = m_a.end()
        j = m_b.end()

    len_a, len_b = len(a) - i, len(b) - j
    if len_a == len_b == 0:
        return 0
    return -1 if len_a < len_b else (1 if len_a > len_b else 0)


def compare_evr(a: str | None, b: str | None) -> int:
    """Compare two "version-release" (or "version-release.dist") labels, the
    shape lib.version.nvr() writes into build-report.db's artifacts.version
    column (e.g. "0.14.2-2.fc44"). Splits each on its last "-" into
    version/release and compares version first, then release, both via
    rpmvercmp -- same precedence as RPM's own EVR comparison (epoch is
    always absent/equal here, so it's skipped).

    None/empty sorts lower than any real label, so an unversioned artifacts
    row never wins a comparison against a versioned one; two Nones/empties
    compare equal.
    """
    if not a and not b:
        return 0
    if not a:
        return -1
    if not b:
        return 1
    ver_a, sep_a, rel_a = a.rpartition("-")
    ver_b, sep_b, rel_b = b.rpartition("-")
    if not sep_a:
        ver_a, rel_a = a, ""
    if not sep_b:
        ver_b, rel_b = b, ""
    result = rpmvercmp(ver_a, ver_b)
    if result != 0:
        return result
    return rpmvercmp(rel_a, rel_b)


def versions_for(packages: dict, stages: dict) -> dict[str, str]:
    """Map package name -> display version, for every package in `packages`.

    `stages` is the {stage: {package: entry}} shape returned by
    lib.build_db.stage_map(target). Uses the same recorded/declared precedence as
    recorded_version().
    """
    return {
        pkg: recorded_version(
            [stages.get(s, {}).get(pkg) for s in VERSION_STAGE_PRECEDENCE], meta
        )
        for pkg, meta in packages.items()
    }
