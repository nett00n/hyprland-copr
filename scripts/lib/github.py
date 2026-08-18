"""GitHub API utilities for release fetching and caching.

Provides functions to:
- Fetch release info from GitHub API with retry logic
- Cache releases locally with TTL
- Build changelog data for Jinja2 templates
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

from lib.paths import GITHUB_RELEASE_CACHE

CACHE_TTL = 7 * 24 * 3600  # 7 days

GITHUB_RETRIES = 3
GITHUB_RETRY_PAUSE = 10  # seconds


def _cache_key(github_url: str, version: str) -> str:
    """Extract owner/repo from GitHub URL and create cache key.

    Args:
        github_url: GitHub repository URL (https://github.com/owner/repo)
        version: Release version

    Returns:
        Cache key in format "owner/repo@version"
    """
    m = re.match(r"https://github\.com/([^/]+/[^/]+)", github_url)
    return f"{m.group(1)}@{version}" if m else f"{github_url}@{version}"


def load_release_cache(url: str, version: str) -> dict | None:
    """Load cached GitHub release info if still valid.

    Args:
        url: GitHub repository URL
        version: Release version

    Returns:
        Cached release dict if found and not expired, None otherwise
    """
    if not GITHUB_RELEASE_CACHE.exists():
        return None
    try:
        data = json.loads(GITHUB_RELEASE_CACHE.read_text())
        entry = data.get(_cache_key(url, version))
        if entry and time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return None


def save_release_cache(url: str, version: str, release: dict) -> None:
    """Save GitHub release info to cache with timestamp.

    Args:
        url: GitHub repository URL
        version: Release version
        release: Release data dict from GitHub API
    """
    GITHUB_RELEASE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = (
            json.loads(GITHUB_RELEASE_CACHE.read_text())
            if GITHUB_RELEASE_CACHE.exists()
            else {}
        )
    except (json.JSONDecodeError, OSError):
        data = {}
    now = time.time()
    data = {
        key: entry
        for key, entry in data.items()
        if now - entry.get("timestamp", 0) < CACHE_TTL
    }
    data[_cache_key(url, version)] = {"data": release, "timestamp": int(now)}
    GITHUB_RELEASE_CACHE.write_text(json.dumps(data, indent=2))


def fetch_github_release(github_url: str, version: str) -> dict | None:
    """Fetch release info from GitHub API with retry logic and caching.

    Attempts to load from cache first, then fetches from GitHub API if needed.
    Retries on transient errors (429, 5xx, network errors) but not permanent
    client errors (4xx except 429).

    Args:
        github_url: GitHub repository URL (https://github.com/owner/repo)
        version: Release version to fetch

    Returns:
        Release dict from GitHub API, or None if fetch fails or not found
    """
    # Check cache first
    cached = load_release_cache(github_url, version)
    if cached:
        return cached

    m = re.match(r"https://github\.com/([^/]+/[^/]+)", github_url)
    if not m:
        return None

    repo = m.group(1)
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    req = urllib.request.Request(
        api_url, headers={"Accept": "application/vnd.github+json"}
    )

    for attempt in range(1, GITHUB_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                release = json.loads(resp.read())
                save_release_cache(github_url, version, release)
                return release
        except urllib.error.HTTPError as e:
            # Don't retry on permanent client errors (4xx) except 429 (rate limit)
            if 400 <= e.code < 500 and e.code != 429:
                print(
                    f"warning: failed to fetch {api_url}: HTTP {e.code}",
                    file=sys.stderr,
                )
                return None
            # Retry on transient errors: 429, 5xx, network errors
            if attempt < GITHUB_RETRIES:
                print(
                    f"warning: github fetch attempt {attempt} failed (HTTP {e.code}), retrying in {GITHUB_RETRY_PAUSE}s",
                    file=sys.stderr,
                )
                time.sleep(GITHUB_RETRY_PAUSE)
            else:
                print(
                    f"warning: failed to fetch {api_url}: HTTP {e.code}",
                    file=sys.stderr,
                )
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            # Retry on network/timeout errors
            if attempt < GITHUB_RETRIES:
                print(
                    f"warning: github fetch attempt {attempt} failed ({e}), retrying in {GITHUB_RETRY_PAUSE}s",
                    file=sys.stderr,
                )
                time.sleep(GITHUB_RETRY_PAUSE)
            else:
                print(f"warning: failed to fetch {api_url}: {e}", file=sys.stderr)
    return None


def build_changelog(
    release_info: dict | None,
    version: str,
    release: int | str,
    packager: str,
    source_url: str | None = None,
    copr_url: str | None = None,
) -> dict:
    """Build structured changelog data for Jinja2 template.

    Extracts release date, tag, commit, and notes from GitHub release info.
    Falls back to current date and default note if release info unavailable.

    Args:
        release_info: Release dict from GitHub API (or None)
        version: Release version string
        release: Release number for RPM spec
        packager: Packager name/email for changelog entry
        source_url: Optional source URL for the entry
        copr_url: Optional COPR build URL for the entry

    Returns:
        Dictionary with changelog data for template context
    """
    if release_info and release_info.get("published_at"):
        dt = datetime.fromisoformat(release_info["published_at"].replace("Z", "+00:00"))
    else:
        dt = datetime.now(timezone.utc)

    # Normalise tag/commit across local-git and GitHub-API sources
    tag = (
        (release_info.get("tag") or release_info.get("tag_name"))
        if release_info
        else None
    )
    commit = release_info.get("commit") if release_info else None

    # Parse body into clean note strings (strip markdown bullets/headings)
    notes: list[str] = []
    body = release_info.get("body") if release_info else None
    if body:
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("- ", "* ", "• ")):
                notes.append(line[2:].strip())
            else:
                notes.append(line)
    if not notes:
        notes.append(f"Update to {version}")

    return {
        "date": dt.strftime("%a %b %d %Y"),
        "packager": packager,
        "version": str(version),
        "release": release,
        "tag": tag,
        "commit": commit,
        "notes": notes,
        "source_url": source_url,
        "copr_url": copr_url,
    }
