#!/usr/bin/env python3
"""Fetch latest tags for submodules and update versions in packages.yaml.

Prints a YAML summary of latest versions to stdout.
Reports changed packages to stderr.

Usage:
    python3 scripts/update-versions.py
"""

import sys

import yaml

from lib.gitmodules import fetch_tags, get_submodule_commit, parse_gitmodules
from lib.paths import GITMODULES, PACKAGES_YAML, ROOT
from lib.subprocess_utils import run_git
from lib.version import latest_semver
from lib.yaml_utils import pop_build_stages, write_yaml_preserving_comments


def pull_submodule(mod: dict) -> None:
    """Run git pull inside the submodule directory, reporting result to stderr."""
    repo = ROOT / mod["path"]
    if not repo.exists():
        print(f"  warning: {repo} does not exist, skipping pull", file=sys.stderr)
        return
    result = run_git("pull", cwd=repo)
    if result.returncode != 0:
        print(f"  warning: git pull failed for {mod['name']}", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
    else:
        summary = (
            result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "ok"
        )
        print(f"  pulled {mod['name']}: {summary}", file=sys.stderr)


def main() -> None:
    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)

    print("pulling submodules ...", file=sys.stderr)
    for mod in modules:
        pull_submodule(mod)

    url_to_latest: dict[str, str] = {}
    url_to_commit_info: dict[str, tuple[str, str, str]] = {}

    for mod in modules:
        print(f"fetching tags: {mod['name']} ...", file=sys.stderr)
        tags = fetch_tags(mod["url"])
        latest = latest_semver(tags)
        if latest:
            url_to_latest[mod["url"]] = latest.lstrip("v")
        else:
            repo = ROOT / mod["path"]
            commit_info = get_submodule_commit(repo)
            if commit_info:
                url_to_commit_info[mod["url"]] = commit_info

    # Print summary YAML to stdout
    summary = {}
    for mod in modules:
        url = mod["url"]
        if url in url_to_latest:
            latest_str: str | None = url_to_latest[url]
        elif url in url_to_commit_info:
            _, short, date = url_to_commit_info[url]
            latest_str = f"0^{date}git{short}"
        else:
            latest_str = None
        summary[mod["name"]] = {"url": url, "latest": latest_str}
    print(
        yaml.dump(
            summary,
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
            indent=2,
            width=1000,
        )
    )

    if not PACKAGES_YAML.exists():
        print(f"warning: {PACKAGES_YAML} not found, skipping update", file=sys.stderr)
        return

    changed = write_yaml_preserving_comments(
        PACKAGES_YAML, url_to_latest, url_to_commit_info
    )
    if changed:
        print("updated packages.yaml:", file=sys.stderr)
        for pkg, (old, new) in sorted(changed.items()):
            print(f"  {pkg}: {old} -> {new}", file=sys.stderr)

        affected = pop_build_stages(changed)
        print(
            f"cleared mock/copr build status for: {', '.join(affected)}",
            file=sys.stderr,
        )
    else:
        print("packages.yaml: all versions already up to date", file=sys.stderr)


if __name__ == "__main__":
    main()
