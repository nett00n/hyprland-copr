"""Gitmodules parsing and submodule utilities."""

import configparser
import subprocess
import sys
from pathlib import Path


def parse_gitmodules(path: Path) -> list[dict]:
    """Parse .gitmodules and return list of {name, path, url} dicts."""
    parser = configparser.ConfigParser()
    parser.read(path)
    modules = []
    for section in parser.sections():
        name = section.removeprefix('submodule "').removesuffix('"')
        modules.append(
            {
                "name": name,
                "path": parser[section].get("path", ""),
                "url": parser[section].get("url", ""),
            }
        )
    return modules


def fetch_tags(url: str) -> list[str]:
    """Fetch all tags from a remote git URL."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"  warning: failed to fetch tags from {url}", file=sys.stderr)
            return []
        tags = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            ref = parts[1]
            if ref.endswith("^{}"):
                continue
            tags.append(ref.removeprefix("refs/tags/"))
        return tags
    except subprocess.TimeoutExpired:
        print(f"  warning: timeout fetching tags from {url}", file=sys.stderr)
        return []


def resolve_module(modules: list[dict], name: str) -> dict | None:
    """Find a module whose path's last component matches name (case-insensitive)."""
    name_lower = name.lower()
    for mod in modules:
        if Path(mod["path"]).name.lower() == name_lower:
            return mod
    return None


def get_submodule_commit(repo: Path) -> tuple[str, str, str] | None:
    """Return (full_hash, short_hash, date_YYYYMMDD) for HEAD of the submodule."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "log",
                "-1",
                "--format=%H %cd",
                "--date=format:%Y%m%d",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        parts = result.stdout.strip().split()
        if len(parts) < 2:
            return None
        full_hash, date_str = parts[0], parts[1]
        return full_hash, full_hash[:7], date_str
    except Exception:
        return None
