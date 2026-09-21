"""Gitmodules parsing and submodule utilities.

All git subprocess access goes through lib.subprocess_utils.run_git rather than
calling subprocess.run directly, so it inherits run_git's timeout defaults and
its no-raise contract (see that function's docstring).
"""

import configparser
import sys
from pathlib import Path
from typing import NamedTuple

from .subprocess_utils import run_git


class TagFetch(NamedTuple):
    """Result of fetch_tags(): tags plus whether the fetch itself failed.

    error is None on success (including "no tags at all", which is not an
    error). A non-None error means the tag list is not trustworthy -- an empty
    `tags` list must not be read as "upstream has no tags" in that case. See
    docs/BUGS.md formerly BUG-0100: fetch/timeout failures used to return the
    same `[]` as a tagless repo, hiding a network failure as silently as a
    tagless upstream.
    """

    tags: list[str]
    error: str | None = None


def parse_gitmodules(path: Path) -> list[dict]:
    """Parse .gitmodules and return list of {name, path, url, ignore} dicts.

    `ignore` is `None` when the section has no `ignore =` line at all (as
    opposed to `""`, which would mean an explicit-but-empty value) -- callers
    that check for "missing ignore=dirty" (see lib.validation.validate_gitmodules,
    docs/BUGS.md formerly BUG-0012) need to tell the two apart.
    """
    parser = configparser.ConfigParser(strict=False)
    parser.read(path)
    modules = []
    for section in parser.sections():
        name = section.removeprefix('submodule "').removesuffix('"')
        modules.append(
            {
                "name": name,
                "path": parser[section].get("path", ""),
                "url": parser[section].get("url", ""),
                "ignore": parser[section].get("ignore", None),
            }
        )
    return modules


def fetch_tags(url: str) -> TagFetch:
    """Fetch all tags from a remote git URL.

    Returns TagFetch(tags, error) -- error is set (and tags is []) when the
    fetch itself failed, so callers can tell that apart from an upstream that
    legitimately has no tags. See TagFetch's docstring / BUG-0100.
    """
    result = run_git("ls-remote", "--tags", url, timeout=30)
    if result.returncode == 124:
        error = f"timeout fetching tags from {url}"
        print(f"  warning: {error}", file=sys.stderr)
        return TagFetch([], error)
    if result.returncode != 0:
        error = f"failed to fetch tags from {url}"
        print(f"  warning: {error}", file=sys.stderr)
        return TagFetch([], error)
    tags = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1]
        if ref.endswith("^{}"):
            continue
        tags.append(ref.removeprefix("refs/tags/"))
    return TagFetch(tags)


def ensure_initialized(root: Path, modules: list[dict], urls: set[str]) -> list[str]:
    """Auto-init any submodule in `modules` whose url is in `urls` and isn't checked
    out yet (fresh clone without --recurse-submodules leaves an empty placeholder
    directory). Returns the paths that were initialized; empty if all were already
    checked out or nothing matched.

    Uses `git submodule status` to detect the uninitialized case (a leading '-' in
    its output) rather than checking directory emptiness directly, since that's
    git's own notion of "not initialized" and matches what `submodule update --init`
    would act on.
    """
    paths = [mod["path"] for mod in modules if mod["url"] in urls and mod["path"]]
    if not paths:
        return []

    status = run_git("-C", str(root), "submodule", "status", "--", *paths)
    if status.returncode != 0:
        return []

    uninitialized = [
        line[1:].split()[1]
        for line in status.stdout.splitlines()
        if line.startswith("-")
    ]
    if not uninitialized:
        return []

    update = run_git(
        "-C", str(root), "submodule", "update", "--init", "--", *uninitialized
    )
    if update.returncode != 0:
        raise RuntimeError(
            f"git submodule update --init failed (exit {update.returncode}): "
            f"{update.stderr.strip()}"
        )
    return uninitialized


def resolve_module(modules: list[dict], name: str) -> dict | None:
    """Find a module whose path's last component matches name (case-insensitive)."""
    name_lower = name.lower()
    for mod in modules:
        if Path(mod["path"]).name.lower() == name_lower:
            return mod
    return None


def get_tag_info(repo: Path, version: str) -> dict | None:
    """Return {published_at, body, tag, commit} for a version tag in the submodule.

    Tries annotated tag message first (git cat-file tag), then falls back to
    the commit log message. Returns None if the tag does not exist.
    """
    import datetime

    tag = f"v{version}"

    check = run_git("-C", str(repo), "tag", "-l", tag)
    if not check.stdout.strip():
        # Tag not found locally — try fetching it from the remote
        run_git("-C", str(repo), "fetch", "origin", "tag", tag, timeout=30)
        check = run_git("-C", str(repo), "tag", "-l", tag)
        if not check.stdout.strip():
            return None

    published_at = None
    body = None

    # Try annotated tag first
    cat = run_git("-C", str(repo), "cat-file", "tag", tag)
    if cat.returncode == 0 and cat.stdout:
        lines = cat.stdout.splitlines()
        blank = next((i for i, line in enumerate(lines) if line == ""), len(lines))
        header_lines = lines[:blank]
        message_lines = lines[blank + 1 :]
        for line in header_lines:
            if line.startswith("tagger "):
                parts = line.split()
                try:
                    ts = int(parts[-2])
                    published_at = datetime.datetime.fromtimestamp(
                        ts, tz=datetime.timezone.utc
                    ).isoformat()
                except (ValueError, IndexError):
                    pass
                break
        body = "\n".join(message_lines).strip() or None

    # Fall back to commit log for missing date or body
    if not published_at or not body:
        log = run_git("-C", str(repo), "log", "-1", "--format=%aI%n%B", tag)
        if log.returncode == 0 and log.stdout:
            log_lines = log.stdout.splitlines()
            if not published_at and log_lines:
                published_at = log_lines[0].strip()
            if not body:
                body = "\n".join(log_lines[1:]).strip() or None

    if not published_at:
        return None

    # Resolve tag to its commit hash (dereferences annotated tags)
    rev = run_git("-C", str(repo), "rev-list", "-n1", tag)
    commit = rev.stdout.strip() if rev.returncode == 0 else None

    return {"published_at": published_at, "body": body, "tag": tag, "commit": commit}


def get_commit_info(repo: Path, ref: str = "HEAD") -> dict | None:
    """Return {published_at, body, commit} from a commit's log message.

    published_at is the author ISO timestamp; body is the commit message body;
    commit is the full SHA-1 hash.
    """
    import datetime

    log = run_git("-C", str(repo), "log", "-1", "--format=%H%n%aI%n%B", ref)
    if log.returncode != 0 or not log.stdout:
        return None
    lines = log.stdout.splitlines()
    commit = lines[0].strip() if lines else None
    published_at = lines[1].strip() if len(lines) > 1 else None
    body = "\n".join(lines[2:]).strip() or None
    if not published_at:
        return None
    # Validate it looks like a date
    try:
        datetime.datetime.fromisoformat(published_at)
    except ValueError:
        return None
    return {"published_at": published_at, "body": body, "commit": commit}


def get_changelog_info(
    repo: Path, version: str, commit_hash: str | None = None
) -> dict | None:
    """Return {published_at, body, tag, commit} for changelog generation.

    Tries the version tag first (annotated or lightweight), fetching it from
    the remote if not found locally.  Falls back to commit_hash log if given
    (for commit-based packages).  Returns None otherwise so callers can try
    the GitHub release API instead.
    """
    tag_info = get_tag_info(repo, version)
    if tag_info:
        return tag_info
    if commit_hash:
        return get_commit_info(repo, commit_hash)
    return None


def get_submodule_commit(repo: Path, ref: str = "HEAD") -> tuple[str, str, str] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD) for `ref` in the submodule.

    `ref` defaults to the checked-out HEAD; update-versions.py passes
    "origin/<branch>" so a package's version never depends on where the working
    tree happens to sit (a pinned sibling can share the same checkout without
    its version resolution being affected -- see docs/BUGS.md BUG-0033).
    """
    result = run_git(
        "-C", str(repo), "log", "-1", "--format=%H %cd", "--date=format:%Y%m%d", ref
    )
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) < 2:
        return None
    full_hash, date_str = parts[0], parts[1]
    return full_hash, full_hash[:7], date_str


def get_submodule_commit_with_base(
    repo: Path, ref: str = "HEAD"
) -> tuple[str, str, str, str | None] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD, base_semver | None) for `ref`.

    base_semver is the nearest reachable semver tag (v-prefix stripped), or None.
    """
    commit_info = get_submodule_commit(repo, ref)
    if not commit_info:
        return None

    full_hash, short_hash, date_str = commit_info

    # Find nearest semver tag. Describe from the resolved commit hash rather than
    # `ref` itself, so this can't disagree with get_submodule_commit() above if
    # a remote-tracking ref moves between the two subprocess calls.
    base_semver: str | None = None
    result = run_git(
        "-C",
        str(repo),
        "describe",
        "--tags",
        "--match",
        "v*.*.*",
        "--abbrev=0",
        full_hash,
        timeout=10,
    )
    if result.returncode == 0 and result.stdout.strip():
        tag = result.stdout.strip()
        base_semver = tag.lstrip("v")

    return full_hash, short_hash, date_str, base_semver


def get_tag_commit(repo: Path, tag: str) -> tuple[str, str, str, str | None] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD, base_semver | None) for a tag.

    Resolves the tag to its commit and extracts commit info and nearest semver base.
    """
    # Resolve tag to full commit hash
    rev_result = run_git(
        "-C", str(repo), "rev-list", "-n1", f"refs/tags/{tag}", timeout=10
    )
    if rev_result.returncode != 0 or not rev_result.stdout.strip():
        return None

    full_hash = rev_result.stdout.strip()

    # Get date of the commit
    date_result = run_git(
        "-C",
        str(repo),
        "log",
        "-1",
        "--format=%cd",
        "--date=format:%Y%m%d",
        full_hash,
        timeout=10,
    )
    if date_result.returncode != 0 or not date_result.stdout.strip():
        return None

    date_str = date_result.stdout.strip()

    # Find nearest semver tag from this commit
    base_semver: str | None = None
    describe_result = run_git(
        "-C",
        str(repo),
        "describe",
        "--tags",
        "--match",
        "v*.*.*",
        "--abbrev=0",
        full_hash,
        timeout=10,
    )
    if describe_result.returncode == 0 and describe_result.stdout.strip():
        base_tag = describe_result.stdout.strip()
        base_semver = base_tag.lstrip("v")

    return full_hash, full_hash[:7], date_str, base_semver
