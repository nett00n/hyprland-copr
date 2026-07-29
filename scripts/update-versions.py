#!/usr/bin/env python3
"""Fetch latest tags for submodules and update versions in packages.yaml.

Prints a YAML summary of latest versions to stdout.
Reports changed packages to stderr.

Usage:
    python3 scripts/update-versions.py
"""

import sys

import yaml

from lib.gitmodules import (
    fetch_tags,
    get_submodule_commit_with_base,
    get_tag_commit,
    parse_gitmodules,
)
from lib.paths import GITMODULES, PACKAGES_YAML, ROOT
from lib.subprocess_utils import run_git
from lib.version import latest_semver
from lib.yaml_utils import (
    get_packages,
    write_yaml_preserving_comments,
)


def pull_submodule(mod: dict, branch: str | None = None) -> None:
    """Fetch and checkout branch, overriding any local state.

    If branch is None, uses the default branch from origin's HEAD.
    Otherwise, checks out the specified branch.
    """
    repo = ROOT / mod["path"]
    if not repo.exists():
        print(f"  warning: {repo} does not exist, skipping pull", file=sys.stderr)
        return

    # Fetch latest from origin
    fetch_result = run_git("fetch", "origin", cwd=repo)
    if fetch_result.returncode != 0:
        print(f"  warning: git fetch failed for {mod['name']}", file=sys.stderr)
        if fetch_result.stderr:
            print(f"  {fetch_result.stderr.strip()}", file=sys.stderr)
        return

    # Determine target branch
    target_branch = branch
    if target_branch is None:
        # Get the default branch from origin's HEAD
        head_result = run_git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=repo)
        if head_result.returncode != 0:
            print(
                f"  warning: could not determine default branch for {mod['name']}",
                file=sys.stderr,
            )
            return
        # Extract branch name from "refs/remotes/origin/main" -> "main"
        target_branch = head_result.stdout.strip().split("/")[-1]

    # Checkout and sync with origin
    checkout_result = run_git(
        "switch", "-C", target_branch, f"origin/{target_branch}", cwd=repo
    )
    if checkout_result.returncode != 0:
        print(f"  warning: git switch failed for {mod['name']}", file=sys.stderr)
        if checkout_result.stderr:
            print(f"  {checkout_result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  updated {mod['name']} to {target_branch}", file=sys.stderr)


def main() -> None:
    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)
    url_to_module = {mod["url"]: mod for mod in modules}

    # Load packages.yaml. Config/versions below are keyed by PACKAGE NAME, not
    # url: multiple packages (e.g. Hyprland / Hyprland-git) can legitimately
    # point at the same submodule url but need independent release_type
    # handling. Keying by url let one package's config silently shadow
    # another's (see docs/bugs.md).
    packages: dict = {}
    if PACKAGES_YAML.exists():
        try:
            packages = get_packages(PACKAGES_YAML)
        except SystemExit:
            # get_packages exits on error; ignore and continue
            pass

    # One physical checkout per submodule url: the branch to check it out to
    # comes from whichever package(s) pointing at that url specify one.
    url_to_branch: dict[str, str | None] = {}
    for pkg_data in packages.values():
        url = pkg_data.get("url", "")
        auto_update = pkg_data.get("auto_update") or {}
        if url in url_to_module:
            url_to_branch[url] = auto_update.get("branch")

    print("pulling submodules ...", file=sys.stderr)
    for mod in modules:
        pull_submodule(mod, branch=url_to_branch.get(mod["url"]))

    pkg_to_latest: dict[str, str] = {}
    pkg_to_commit_info: dict[str, tuple[str, str, str, str | None]] = {}

    for pkg_name, pkg_data in packages.items():
        url = pkg_data.get("url", "")
        mod = url_to_module.get(url)
        if mod is None:
            continue
        auto_update = pkg_data.get("auto_update") or {}
        release_type = auto_update.get("release_type", "")
        repo = ROOT / mod["path"]

        # Handle pinned versions/commits - skip update
        if release_type == "pinned-version":
            continue
        if release_type == "pinned-commit":
            continue

        # Handle pinned-tag
        if release_type == "pinned-tag":
            tag = auto_update.get("tag")
            if tag:
                print(
                    f"fetching pinned tag: {pkg_name} (tag={tag}) ...",
                    file=sys.stderr,
                )
                commit_info = get_tag_commit(repo, tag)
                if commit_info:
                    pkg_to_commit_info[pkg_name] = commit_info
            continue

        # Handle latest-version (semver only, no commit fallback)
        if release_type == "latest-version":
            print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
            tags = fetch_tags(url)
            latest = latest_semver(tags)
            if latest:
                pkg_to_latest[pkg_name] = latest.lstrip("v")
            continue

        # Handle latest-commit
        if release_type == "latest-commit":
            print(f"fetching HEAD commit: {pkg_name} ...", file=sys.stderr)
            commit_info = get_submodule_commit_with_base(repo)
            if commit_info:
                pkg_to_commit_info[pkg_name] = commit_info
            continue

        # Default: try semver, fall back to commit
        print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
        tags = fetch_tags(url)
        latest = latest_semver(tags)
        if latest:
            pkg_to_latest[pkg_name] = latest.lstrip("v")
        else:
            commit_info = get_submodule_commit_with_base(repo)
            if commit_info:
                pkg_to_commit_info[pkg_name] = commit_info

    # Print summary YAML to stdout
    summary = {}
    for pkg_name, pkg_data in packages.items():
        if pkg_name in pkg_to_latest:
            latest_str: str | None = pkg_to_latest[pkg_name]
        elif pkg_name in pkg_to_commit_info:
            full_hash, short, date, base = pkg_to_commit_info[pkg_name]
            prefix = base if base else "0"
            latest_str = f"{prefix}^{date}git{short}"
        else:
            latest_str = None
        summary[pkg_name] = {"url": pkg_data.get("url", ""), "latest": latest_str}
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
        PACKAGES_YAML, pkg_to_latest, pkg_to_commit_info
    )
    if changed:
        print("updated packages.yaml:", file=sys.stderr)
        for pkg, (old, new) in sorted(changed.items()):
            print(f"  {pkg}: {old} -> {new}", file=sys.stderr)
    else:
        print("packages.yaml: all versions already up to date", file=sys.stderr)


if __name__ == "__main__":
    main()
