"""Upstream mirror cache and git metadata helpers. #COPR-0004

Upstream sources live in a disposable, gitignored cache under
`lib.paths.UPSTREAM_DIR` (`.cache/upstream/`): per distinct packages.yaml `url`, a
bare mirror (`<org>/<name>.git`, fetch refspecs `+refs/heads/*:refs/remotes/origin/*`
and `+refs/tags/*:refs/tags/*`) plus a detached worktree of it (`<org>/<name>`).
Nothing here is tracked by the superproject.

All git subprocess access goes through lib.subprocess_utils.run_git rather than
calling subprocess.run directly, so it inherits run_git's timeout defaults and
its no-raise contract (see that function's docstring).
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

from . import paths
from .subprocess_utils import run_git


class UpstreamError(RuntimeError):
    """A mirror could not be created, fetched or checked out."""


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


def upstream_name(url: str) -> str:
    """Return the `<org>/<name>` cache key for a git url. #COPR-0004

    Takes the last two path segments (without a trailing `.git`); a url with a single
    segment is keyed `<host>/<name>`.
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    if segments and segments[-1].endswith(".git"):
        segments[-1] = segments[-1][: -len(".git")]
    if len(segments) >= 2:
        return "/".join(segments[-2:])
    host = parsed.netloc or "local"
    return f"{host}/{segments[-1] if segments else 'unknown'}"


def mirror_path(url: str) -> Path:
    """Path of the bare mirror for `url`. #COPR-0004"""
    return paths.UPSTREAM_DIR / f"{upstream_name(url)}.git"


def worktree_path(url: str) -> Path:
    """Path of the detached worktree for `url`. #COPR-0004"""
    return paths.UPSTREAM_DIR / upstream_name(url)


def _relative_to_root(path: Path) -> str:
    try:
        return path.relative_to(paths.ROOT).as_posix()
    except ValueError:
        return str(path)


def upstream_entry(url: str) -> dict:
    """Registry entry {name, path, url} for one url. #COPR-0004"""
    return {
        "name": upstream_name(url),
        "path": _relative_to_root(worktree_path(url)),
        "url": url,
    }


def list_upstreams(packages: dict) -> list[dict]:
    """Registry of upstreams: one {name, path, url} per distinct package `url`.

    #COPR-0004. `path` is the worktree path relative to the repo root (the shape
    callers used to read from .gitmodules). Sorted by url for stable output.
    """
    urls = {
        meta["url"]
        for meta in packages.values()
        if isinstance(meta, dict) and meta.get("url")
    }
    return [upstream_entry(url) for url in sorted(urls)]


def find_upstream(name: str) -> dict | None:
    """Find a cached mirror by its repo name (case-insensitive). #COPR-0004

    Used for packages that are not in packages.yaml yet (scaffold-package). Reads the
    mirror's own `remote.origin.url`, so the returned entry has the original url.
    """
    if not paths.UPSTREAM_DIR.is_dir():
        return None
    wanted = name.lower()
    for mirror in sorted(paths.UPSTREAM_DIR.glob("*/*.git")):
        if mirror.name.removesuffix(".git").lower() != wanted:
            continue
        result = run_git(
            "-C", str(mirror), "config", "--get", "remote.origin.url", timeout=10
        )
        url = result.stdout.strip()
        if result.returncode == 0 and url:
            return upstream_entry(url)
    return None


def _git_error(result: subprocess.CompletedProcess, what: str) -> str:
    detail = result.stderr.strip() or f"exit {result.returncode}"
    return f"{what}: {detail}"


def _mirror_is_healthy(mirror: Path) -> bool:
    if not mirror.is_dir():
        return False
    result = run_git("-C", str(mirror), "rev-parse", "--is-bare-repository", timeout=10)
    return result.returncode == 0 and result.stdout.strip() == "true"


def ensure_mirror(url: str) -> str | None:
    """Create the bare mirror for `url` if missing or corrupt. #COPR-0004

    Returns None on success or an error message. A corrupt mirror (not a valid bare
    repo any more) is deleted and re-initialised; the cache holds no state, so that
    only costs a re-fetch.
    """
    mirror = mirror_path(url)
    if _mirror_is_healthy(mirror):
        return None
    if mirror.exists():
        shutil.rmtree(mirror, ignore_errors=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    steps = (
        ("init", "--bare", "-q", str(mirror)),
        ("-C", str(mirror), "remote", "add", "origin", url),
        (
            "-C",
            str(mirror),
            "config",
            "--replace-all",
            "remote.origin.fetch",
            "+refs/heads/*:refs/remotes/origin/*",
        ),
        (
            "-C",
            str(mirror),
            "config",
            "--add",
            "remote.origin.fetch",
            "+refs/tags/*:refs/tags/*",
        ),
        # Relative worktree paths so the same tree resolves on the host and under
        # the /work container bind mount (git >= 2.48).
        ("-C", str(mirror), "config", "worktree.useRelativePaths", "true"),
    )
    for step in steps:
        result = run_git(*step, timeout=60)
        if result.returncode != 0:
            return _git_error(result, f"could not create mirror for {url}")
    return None


def fetch_mirror(url: str) -> str | None:
    """Create (if needed) and fetch the mirror for `url`. #COPR-0004

    Fetches branches and tags (pruning deleted ones) and points `origin/HEAD` at the
    remote's default branch. Returns None on success or an error message; a failed
    fetch leaves the existing mirror in place.
    """
    error = ensure_mirror(url)
    if error:
        return error
    mirror = mirror_path(url)
    fetch = run_git(
        "-C", str(mirror), "fetch", "--tags", "--prune", "origin", timeout=300
    )
    if fetch.returncode != 0:
        return _git_error(fetch, f"git fetch failed for {url}")
    # Best effort: a repo with no commits has no default branch to point at.
    run_git("-C", str(mirror), "remote", "set-head", "origin", "--auto", timeout=60)
    return None


def checkout_worktree(url: str, ref: str) -> str | None:
    """Position the detached worktree for `url` at `ref`. #COPR-0004

    `ref` is anything resolvable in the mirror (`origin/<branch>`, `refs/tags/X`, a
    commit). Creates the worktree on first use, force-moves it afterwards, and cleans
    untracked files, so it never stays dirty. Returns None on success or an error.
    """
    mirror = mirror_path(url)
    worktree = worktree_path(url)
    resolved = run_git(
        "-C",
        str(mirror),
        "rev-parse",
        "--verify",
        "--quiet",
        f"{ref}^{{commit}}",
        timeout=10,
    )
    sha = resolved.stdout.strip()
    if resolved.returncode != 0 or not sha:
        return f"cannot resolve {ref} in {mirror}"

    attached = worktree.is_dir() and (worktree / ".git").exists()
    if attached:
        move = run_git(
            "-C", str(worktree), "checkout", "--force", "--detach", sha, timeout=120
        )
        if move.returncode == 0:
            clean = run_git("-C", str(worktree), "clean", "-ffdx", timeout=120)
            if clean.returncode != 0:
                return _git_error(clean, f"git clean failed in {worktree}")
            return None
        # Fall through: a broken worktree is recreated below.
    if worktree.exists():
        shutil.rmtree(worktree, ignore_errors=True)
    run_git("-C", str(mirror), "worktree", "prune", timeout=60)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    add = run_git(
        "-C",
        str(mirror),
        "worktree",
        "add",
        "--force",
        "--detach",
        str(worktree),
        sha,
        timeout=120,
    )
    if add.returncode != 0:
        return _git_error(add, f"git worktree add failed for {url}")
    return None


def sync_upstream(url: str, ref: str | None = None) -> Path:
    """Fetch the mirror and check the worktree out at `ref`; return the worktree.

    #COPR-0004. `ref` defaults to the remote's default branch (`origin/HEAD`).
    Raises UpstreamError when the mirror can't be fetched or the ref can't be
    checked out.
    """
    error = fetch_mirror(url)
    if error:
        raise UpstreamError(error)
    target = ref
    if target is None:
        head = run_git(
            "-C",
            str(mirror_path(url)),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            timeout=10,
        )
        if head.returncode != 0 or not head.stdout.strip():
            raise UpstreamError(f"could not determine default branch of {url}")
        target = head.stdout.strip().removeprefix("refs/remotes/")
    error = checkout_worktree(url, target)
    if error:
        raise UpstreamError(error)
    return worktree_path(url)


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


def resolve_module(modules: list[dict], name: str) -> dict | None:
    """Find an upstream whose path's last component matches name (case-insensitive).

    #COPR-0004
    """
    name_lower = name.lower()
    for mod in modules:
        if Path(mod["path"]).name.lower() == name_lower:
            return mod
    return None


def get_tag_info(repo: Path, version: str) -> dict | None:
    """Return {published_at, body, tag, commit} for a version tag in the upstream repo.

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


def get_commit(repo: Path, ref: str = "HEAD") -> tuple[str, str, str] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD) for `ref` in the upstream repo.

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


def get_commit_with_base(
    repo: Path, ref: str = "HEAD"
) -> tuple[str, str, str, str | None] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD, base_semver | None) for `ref`.

    base_semver is the nearest reachable semver tag (v-prefix stripped), or None.
    """
    commit_info = get_commit(repo, ref)
    if not commit_info:
        return None

    full_hash, short_hash, date_str = commit_info

    # Find nearest semver tag. Describe from the resolved commit hash rather than
    # `ref` itself, so this can't disagree with get_commit() above if
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
