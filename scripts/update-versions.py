#!/usr/bin/env python3
"""Fetch latest tags for submodules and update versions in packages.yaml.

Prints a YAML summary of latest versions to stdout.
Reports changed packages to stderr.

Usage:
    python3 scripts/update-versions.py
"""

import sys
from typing import NamedTuple

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

# Types that pin the *checkout*, not just the version string. Exact membership
# on purpose, never startswith("pinned-"): an unknown/misspelled type must
# behave identically here and in the version-resolution loop below, which
# falls through to the default path. See docs/bugs.md BUG-0014 (mpvpaper's
# `latest-tag`); docs/packaging.md holds the canonical release_type table.
PINNED_RELEASE_TYPES = frozenset({"pinned-version", "pinned-commit", "pinned-tag"})


class Pin(NamedTuple):
    """A submodule checkout target derived from a package's pinned release_type.

    kind:       "tag" | "commit" | "version" | "unresolved"
    candidates: commit-ishes to try in order, first that resolves wins; empty
                when kind == "unresolved"
    owner:      package name the pin came from (for warnings)
    detail:     why the pin is unresolved (only set when kind == "unresolved")
    """

    kind: str
    candidates: tuple[str, ...]
    owner: str
    detail: str = ""


def checkout_pin(pkg_name: str, pkg_data: dict) -> "Pin | None":
    """Return the Pin this package imposes on its submodule checkout, or None.

    None means "this package does not pin the checkout" -- the submodule
    tracks its branch as before. A Pin with kind == "unresolved" means the
    package IS pinned but the target can't be derived from packages.yaml; the
    checkout is then left exactly where it is (never falls back to branch
    HEAD -- see docs/bugs.md BUG-0033).
    """
    auto_update = pkg_data.get("auto_update") or {}
    release_type = auto_update.get("release_type", "")
    if release_type not in PINNED_RELEASE_TYPES:
        return None

    if release_type == "pinned-tag":
        tag = auto_update.get("tag")
        if not tag:
            return Pin("unresolved", (), pkg_name, "pinned-tag with no auto_update.tag")
        return Pin("tag", (f"refs/tags/{tag}",), pkg_name)

    if release_type == "pinned-commit":
        commit = ((pkg_data.get("source") or {}).get("commit") or {}).get("full")
        if not commit:
            return Pin(
                "unresolved", (), pkg_name, "pinned-commit with no source.commit.full"
            )
        return Pin("commit", (str(commit),), pkg_name)

    # pinned-version. Try the v-prefixed tag first (the common case: 34/45
    # packages archive from a v-prefixed tag), then the bare version (6/45
    # packages tag without a v prefix, e.g. Waybar) -- pinned-version skips
    # the version-resolution loop entirely (see below), so nothing downstream
    # would ever correct a miss.
    version = str(pkg_data.get("version", "")).strip()
    if not version:
        return Pin("unresolved", (), pkg_name, "pinned-version with no version")
    return Pin("version", (f"refs/tags/v{version}", f"refs/tags/{version}"), pkg_name)


def pull_submodule(
    mod: dict, branch: str | None = None, pin: "Pin | None" = None
) -> str | None:
    """Fetch origin and position the submodule working tree.

    If pin is None, the submodule is force-switched to `origin/<branch>` as
    before (branch defaults to origin's HEAD when not given). If pin is set,
    the checkout is instead pinned *detached* at the resolved pin target and
    is never moved to branch HEAD -- not even when the pin can't be resolved
    (see docs/bugs.md, BUG-0033's fix).

    Returns the remote-tracking ref ("origin/<branch>") that moving packages
    sharing this submodule's url must resolve their versions against. This is
    returned regardless of what was actually checked out (even on a pinned or
    failed checkout), so a pin on a shared url can't freeze a sibling's
    version resolution. Returns None only when the submodule couldn't be
    prepared at all (missing directory, failed fetch, undeterminable default
    branch).
    """
    repo = ROOT / mod["path"]
    if not repo.exists():
        print(f"  warning: {repo} does not exist, skipping pull", file=sys.stderr)
        return None

    # --tags: a pinned tag need not be reachable from the tracked branch, and
    # get_tag_commit() below resolves refs/tags/<tag> locally.
    fetch_result = run_git("fetch", "--tags", "origin", cwd=repo)
    if fetch_result.returncode != 0:
        print(f"  warning: git fetch failed for {mod['name']}", file=sys.stderr)
        if fetch_result.stderr:
            print(f"  {fetch_result.stderr.strip()}", file=sys.stderr)
        return None

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
            return None
        # Extract branch name from "refs/remotes/origin/main" -> "main"
        target_branch = head_result.stdout.strip().split("/")[-1]

    moving_ref = f"origin/{target_branch}"

    if pin is None:
        # Checkout and sync with origin
        checkout_result = run_git("switch", "-C", target_branch, moving_ref, cwd=repo)
        if checkout_result.returncode != 0:
            print(f"  warning: git switch failed for {mod['name']}", file=sys.stderr)
            if checkout_result.stderr:
                print(f"  {checkout_result.stderr.strip()}", file=sys.stderr)
        else:
            print(f"  updated {mod['name']} to {target_branch}", file=sys.stderr)
        # Return moving_ref even on failure: version resolution reads the
        # remote-tracking ref, which is valid whether or not the tree moved.
        return moving_ref

    if pin.kind == "unresolved":
        print(
            f"  warning: {mod['name']} is pinned by {pin.owner} ({pin.detail}); "
            f"leaving the checkout untouched",
            file=sys.stderr,
        )
        return moving_ref

    resolved: str | None = None
    for candidate in pin.candidates:
        check = run_git(
            "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", cwd=repo
        )
        if check.returncode == 0 and check.stdout.strip():
            resolved = check.stdout.strip()
            target = candidate
            break
    else:
        tried = ", ".join(pin.candidates)
        print(
            f"  warning: {mod['name']} is pinned by {pin.owner} to {tried}, none of "
            f"which exist in the fetched repo; leaving the checkout untouched",
            file=sys.stderr,
        )
        return moving_ref

    checkout_result = run_git("checkout", "--force", "--detach", target, cwd=repo)
    if checkout_result.returncode != 0:
        print(
            f"  warning: git checkout failed for {mod['name']} at pinned {target}",
            file=sys.stderr,
        )
        if checkout_result.stderr:
            print(f"  {checkout_result.stderr.strip()}", file=sys.stderr)
    else:
        print(
            f"  pinned {mod['name']} to {target} ({resolved[:7]}, from {pin.owner})",
            file=sys.stderr,
        )
    return moving_ref


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

    # One physical checkout per submodule url. Three things are derived per
    # url below:
    #  - branch: which branch moving (non-pinned) packages track
    #  - pin:    a pinned package's checkout target; a pin beats every moving
    #            sibling on the same url, which is only safe because version
    #            resolution further down reads origin/<branch>, never the
    #            working tree (see docs/bugs.md BUG-0033)
    #  - movers: packages on this url that do NOT pin (for the coexistence note)
    url_to_branch: dict[str, str | None] = {}
    url_to_pin: dict[str, Pin] = {}
    url_to_movers: dict[str, list[str]] = {}
    for pkg_name, pkg_data in packages.items():
        url = pkg_data.get("url", "")
        if url not in url_to_module:
            continue
        auto_update = pkg_data.get("auto_update") or {}
        branch = auto_update.get("branch")
        if branch:
            url_to_branch[url] = branch
        else:
            url_to_branch.setdefault(url, None)

        pin = checkout_pin(pkg_name, pkg_data)
        if pin is None:
            url_to_movers.setdefault(url, []).append(pkg_name)
            continue
        existing = url_to_pin.get(url)
        if existing is None:
            url_to_pin[url] = pin
        elif existing.candidates != pin.candidates or existing.kind != pin.kind:
            print(
                f"  warning: {url}: {pin.owner} pins this submodule to "
                f"{pin.candidates or '(unresolved)'} but {existing.owner} already "
                f"pinned it to {existing.candidates or '(unresolved)'}; keeping "
                f"{existing.owner}'s (first in packages.yaml)",
                file=sys.stderr,
            )

    print("pulling submodules ...", file=sys.stderr)
    url_to_ref: dict[str, str | None] = {}
    for mod in modules:
        url = mod["url"]
        pin = url_to_pin.get(url)
        movers = url_to_movers.get(url, [])
        if pin is not None and movers:
            print(
                f"  note: {mod['name']} is pinned by {pin.owner}; "
                f"{', '.join(movers)} share this submodule and still resolve their "
                f"versions from the remote branch, without moving the checkout",
                file=sys.stderr,
            )
        url_to_ref[url] = pull_submodule(mod, branch=url_to_branch.get(url), pin=pin)

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
        ref = url_to_ref.get(url)

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
            if ref is None:
                print(
                    f"  warning: {pkg_name}: submodule not pulled, cannot resolve "
                    f"latest commit",
                    file=sys.stderr,
                )
                continue
            print(f"fetching HEAD commit: {pkg_name} ({ref}) ...", file=sys.stderr)
            commit_info = get_submodule_commit_with_base(repo, ref)
            if commit_info:
                pkg_to_commit_info[pkg_name] = commit_info
            continue

        # Default: try semver, fall back to commit
        print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
        tags = fetch_tags(url)
        latest = latest_semver(tags)
        if latest:
            pkg_to_latest[pkg_name] = latest.lstrip("v")
        elif ref is None:
            print(
                f"  warning: {pkg_name}: no semver tag and submodule not pulled, "
                f"nothing to resolve",
                file=sys.stderr,
            )
        else:
            commit_info = get_submodule_commit_with_base(repo, ref)
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
