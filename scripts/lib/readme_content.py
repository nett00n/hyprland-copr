"""Non-build-status content for generated docs: contributors, the news feed, and
per-section visibility. Shared by gen-report.py (full regen, needs build-report.db)
and gen-readme-shell.py (header/footer-only regen, doesn't).
"""

import re
from pathlib import Path

from .subprocess_utils import run_git


def collect_contributors(repo_root: Path) -> list[dict]:
    result = run_git("log", "--format=%an|%ae", cwd=repo_root)
    seen: set[str] = set()
    contributors: list[dict] = []
    if result.returncode != 0:
        return contributors
    for line in result.stdout.splitlines():
        name, _, email = line.partition("|")
        if name in seen:
            continue
        seen.add(name)
        github_user = None
        if email.endswith("@users.noreply.github.com"):
            github_user = email.split("@")[0].split("+")[-1]
        contributors.append({"name": name, "github_user": github_user})
    return contributors


def get_recent_news(repo_root: Path, limit: int = 8) -> list[dict]:
    """Get the `limit` most recent entries from blog/NEWS.md (newest first).

    Each `## YYYY-MM-DD` heading starts one entry; its body is the text up to the
    next `## ` heading or end of file.
    """
    news_file = repo_root / "blog" / "NEWS.md"
    if not news_file.exists():
        return []

    text = news_file.read_text()
    headers = list(re.finditer(r"(?m)^## (.+)$", text))

    entries = []
    for i, header in enumerate(headers[:limit]):
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        entries.append(
            {"date": header.group(1).strip(), "body": text[start:end].strip()}
        )
    return entries


DEFAULT_SECTIONS = {
    "news": True,
    "docs": True,
    "support": True,
    "license": True,
    "authors": True,
    "maintainers": True,
    "contributors": True,
    "additional_info": True,
}


def get_sections(repo: dict) -> dict:
    """Resolve which README sections are enabled, defaulting unset keys to True.

    Configured via `documents.sections` in repo.yaml.
    """
    configured = repo.get("documents", {}).get("sections") or {}
    return {
        key: configured.get(key, default) for key, default in DEFAULT_SECTIONS.items()
    }
