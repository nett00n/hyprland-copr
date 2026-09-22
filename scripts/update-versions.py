#!/usr/bin/env python3
"""Fetch latest tags for submodules and update versions in packages.yaml.

Prints a YAML summary of latest versions to stdout.
Reports changed packages to stderr.

Usage:
    python3 scripts/update-versions.py
"""

import contextlib
import datetime
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NamedTuple

import yaml

from lib.config import env_int
from lib.gitmodules import (
    fetch_tags,
    get_submodule_commit_with_base,
    get_tag_commit,
    parse_gitmodules,
)
from lib.paths import GITMODULES, LOG_DIR, PACKAGES_YAML, ROOT
from lib.subprocess_utils import run_git
from lib.version import (
    PINNED_RELEASE_TYPES,
    RELEASE_TYPES,
    latest_semver,
    latest_tag,
    rpm_version_from_tag,
)
from lib.yaml_utils import (
    get_packages,
    update_package_versions,
)

# PINNED_RELEASE_TYPES/RELEASE_TYPES live in lib/version.py -- the single
# source of truth for every release_type, shared with the validators and
# cache/yaml_utils. See docs/BUGS.md BUG-0014 (mpvpaper's `latest-tag`);
# docs/packaging.md holds the canonical release_type table.


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


class Failure(NamedTuple):
    """#COPR-0004, #BUG-0100: one aggregated entry for the failure report.

    Every warn-and-continue site in this script appends one of these (in
    addition to its existing stderr print) so a single `git fetch` failure --
    or any of the other 10 warn sites -- shows up in the aggregated block
    printed at the end of main(), instead of only scrolling past on stderr.

    scope:  submodule or package name the failure is about
    kind:   a small closed vocabulary grouping failures in the report --
            "missing" (submodule dir absent), "fetch" (git fetch failed),
            "branch" (couldn't determine default branch), "switch" (git
            switch/checkout failed), "pin" (a pinned checkout couldn't be
            resolved), "tags" (fetch_tags() itself failed/timed out -- see
            lib.gitmodules.TagFetch), "resolve" (no version could be derived
            from what was fetched), "config" (a packages.yaml value itself is
            the problem, e.g. an unknown release_type)
    detail: human-readable reason, already stripped of the "  warning: "
            prefix used on stderr
    """

    scope: str
    kind: str
    detail: str


def checkout_pin(pkg_name: str, pkg_data: dict) -> "Pin | None":
    """Return the Pin this package imposes on its submodule checkout, or None.

    None means "this package does not pin the checkout" -- the submodule
    tracks its branch as before. A Pin with kind == "unresolved" means the
    package IS pinned but the target can't be derived from packages.yaml; the
    checkout is then left exactly where it is (never falls back to branch
    HEAD -- see docs/BUGS.md BUG-0033).
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
    mod: dict,
    branch: str | None = None,
    pin: "Pin | None" = None,
    failures: "list[Failure] | None" = None,
) -> str | None:
    """Fetch origin and position the submodule working tree.

    If pin is None, the submodule is force-switched to `origin/<branch>` as
    before (branch defaults to origin's HEAD when not given). If pin is set,
    the checkout is instead pinned *detached* at the resolved pin target and
    is never moved to branch HEAD -- not even when the pin can't be resolved
    (see docs/BUGS.md, BUG-0033's fix).

    Returns the remote-tracking ref ("origin/<branch>") that moving packages
    sharing this submodule's url must resolve their versions against. This is
    returned regardless of what was actually checked out (even on a pinned or
    failed checkout), so a pin on a shared url can't freeze a sibling's
    version resolution. Returns None only when the submodule couldn't be
    prepared at all (missing directory, failed fetch, undeterminable default
    branch).

    failures, when given, collects a Failure alongside every stderr warning
    below -- see Failure's docstring / BUG-0100. It defaults to None (rather
    than a caller-owned list) so direct callers/tests that only care about the
    return value and the stderr trace are unaffected.
    """
    repo = ROOT / mod["path"]
    if not repo.exists():
        detail = f"{repo} does not exist, skipping pull"
        print(f"  warning: {detail}", file=sys.stderr)
        if failures is not None:
            failures.append(Failure(mod["name"], "missing", detail))
        return None

    # --tags: a pinned tag need not be reachable from the tracked branch, and
    # get_tag_commit() below resolves refs/tags/<tag> locally.
    fetch_result = run_git("fetch", "--tags", "origin", cwd=repo)
    if fetch_result.returncode != 0:
        detail = "git fetch failed"
        msg = f"  warning: git fetch failed for {mod['name']}"
        if fetch_result.stderr:
            detail += f": {fetch_result.stderr.strip()}"
            msg += f"\n  {fetch_result.stderr.strip()}"
        # #BUG-0101: one print() call, not two -- under UPDATE_VERSIONS_JOBS>1
        # another thread's output can land between two separate print()
        # calls but never inside one.
        print(msg, file=sys.stderr)
        if failures is not None:
            failures.append(Failure(mod["name"], "fetch", detail))
        return None

    # Determine target branch
    target_branch = branch
    if target_branch is None:
        # Get the default branch from origin's HEAD
        head_result = run_git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=repo)
        if head_result.returncode != 0:
            detail = "could not determine default branch"
            print(
                f"  warning: {detail} for {mod['name']}",
                file=sys.stderr,
            )
            if failures is not None:
                failures.append(Failure(mod["name"], "branch", detail))
            return None
        # Extract branch name from "refs/remotes/origin/main" -> "main"
        target_branch = head_result.stdout.strip().split("/")[-1]

    moving_ref = f"origin/{target_branch}"

    if pin is None:
        # Checkout and sync with origin
        checkout_result = run_git("switch", "-C", target_branch, moving_ref, cwd=repo)
        if checkout_result.returncode != 0:
            detail = "git switch failed"
            msg = f"  warning: git switch failed for {mod['name']}"
            if checkout_result.stderr:
                detail += f": {checkout_result.stderr.strip()}"
                msg += f"\n  {checkout_result.stderr.strip()}"
            print(msg, file=sys.stderr)  # #BUG-0101: one atomic print() call
            if failures is not None:
                failures.append(Failure(mod["name"], "switch", detail))
        else:
            print(f"  updated {mod['name']} to {target_branch}", file=sys.stderr)
        # Return moving_ref even on failure: version resolution reads the
        # remote-tracking ref, which is valid whether or not the tree moved.
        return moving_ref

    if pin.kind == "unresolved":
        detail = f"pinned by {pin.owner} ({pin.detail}); leaving the checkout untouched"
        print(
            f"  warning: {mod['name']} is {detail}",
            file=sys.stderr,
        )
        if failures is not None:
            failures.append(Failure(mod["name"], "pin", detail))
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
        detail = (
            f"pinned by {pin.owner} to {tried}, none of which exist in the "
            f"fetched repo; leaving the checkout untouched"
        )
        print(
            f"  warning: {mod['name']} is {detail}",
            file=sys.stderr,
        )
        if failures is not None:
            failures.append(Failure(mod["name"], "pin", detail))
        return moving_ref

    checkout_result = run_git("checkout", "--force", "--detach", target, cwd=repo)
    if checkout_result.returncode != 0:
        detail = f"git checkout failed at pinned {target}"
        msg = f"  warning: git checkout failed for {mod['name']} at pinned {target}"
        if checkout_result.stderr:
            detail += f": {checkout_result.stderr.strip()}"
            msg += f"\n  {checkout_result.stderr.strip()}"
        print(msg, file=sys.stderr)  # #BUG-0101: one atomic print() call
        if failures is not None:
            failures.append(Failure(mod["name"], "switch", detail))
    else:
        print(
            f"  pinned {mod['name']} to {target} ({resolved[:7]}, from {pin.owner})",
            file=sys.stderr,
        )
    return moving_ref


def _run_parallel(
    jobs: int, worker: "Callable[[Any], None]", items: "list[Any]"
) -> None:
    """#BUG-0101: run `worker(item)` for each of `items`, either serially
    (jobs <= 1 -- also the path every existing ordered-side_effect test in
    tests/test_update_versions.py relies on) or across a `jobs`-worker
    ThreadPoolExecutor. `worker` is expected to mutate shared dicts/lists by
    itself (each item owns a distinct key, so concurrent writes from CPython
    threads need no lock -- see docs/features/COPR-0004-version-auto-bump.md).
    `list(...)` over `.map()` forces every task to finish (and re-raises any
    worker exception) before returning.
    """
    if jobs <= 1 or len(items) <= 1:
        for item in items:
            worker(item)
        return
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        list(executor.map(worker, items))


def _resolve_package_version(
    pkg_name: str,
    pkg_data: dict,
    url_to_module: dict,
    url_to_ref: dict,
    pkg_to_latest: dict,
    pkg_to_commit_info: dict,
    failures: "list[Failure]",
) -> None:
    """Resolve one package's latest version/commit per its
    `auto_update.release_type`, writing the result into `pkg_to_latest` or
    `pkg_to_commit_info` (each package writes only its own key).

    #BUG-0101: this is main()'s per-package Loop B body, extracted so it can
    run under `_run_parallel()` -- it's the embarrassingly parallel half
    (`fetch_tags()` is `git ls-remote` against a URL, no local repo touched),
    and most of the wall-clock time this loop spends is network wait.
    """
    url = pkg_data.get("url", "")
    mod = url_to_module.get(url)
    if mod is None:
        return
    auto_update = pkg_data.get("auto_update") or {}
    release_type = auto_update.get("release_type", "")
    repo = ROOT / mod["path"]
    ref = url_to_ref.get(url)

    # Handle pinned versions/commits - skip update
    if release_type == "pinned-version":
        return
    if release_type == "pinned-commit":
        return

    # Handle pinned-tag
    if release_type == "pinned-tag":
        tag = auto_update.get("tag")
        if tag:
            print(f"fetching pinned tag: {pkg_name} (tag={tag}) ...", file=sys.stderr)
            commit_info = get_tag_commit(repo, tag)
            if commit_info:
                pkg_to_commit_info[pkg_name] = commit_info
        return

    # Handle latest-version (semver only, no commit fallback)
    if release_type == "latest-version":
        print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
        tags, fetch_error = fetch_tags(url)
        if fetch_error:
            failures.append(Failure(pkg_name, "tags", fetch_error))
            return
        latest = latest_semver(tags)
        if latest:
            pkg_to_latest[pkg_name] = latest.lstrip("v")
        return

    # Handle latest-tag (loosest match: any version-like tag, no commit
    # fallback) -- for upstreams that don't tag strict semver, e.g.
    # mpvpaper's "1.9" (two components). See docs/BUGS.md BUG-0014.
    if release_type == "latest-tag":
        print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
        tags, fetch_error = fetch_tags(url)
        if fetch_error:
            failures.append(Failure(pkg_name, "tags", fetch_error))
            return
        latest = latest_tag(tags)
        if latest:
            rpm_version = rpm_version_from_tag(latest)
            if rpm_version != latest.lstrip("v"):
                print(
                    f"  warning: {pkg_name}: tag {latest!r} became version "
                    f"{rpm_version!r} for RPM compatibility; a source.archives "
                    f"entry templated on %{{version}} will not match the tag",
                    file=sys.stderr,
                )
            pkg_to_latest[pkg_name] = rpm_version
        else:
            detail = "no version-like tag found"
            print(f"  warning: {pkg_name}: {detail}", file=sys.stderr)
            failures.append(Failure(pkg_name, "resolve", detail))
        return

    # Handle latest-commit
    if release_type == "latest-commit":
        if ref is None:
            detail = "submodule not pulled, cannot resolve latest commit"
            print(f"  warning: {pkg_name}: {detail}", file=sys.stderr)
            failures.append(Failure(pkg_name, "resolve", detail))
            return
        print(f"fetching HEAD commit: {pkg_name} ({ref}) ...", file=sys.stderr)
        commit_info = get_submodule_commit_with_base(repo, ref)
        if commit_info:
            pkg_to_commit_info[pkg_name] = commit_info
        return

    # Unrecognized release_type: falls through to the default path below,
    # same as before, but now says so -- `make validate-packages` rejects
    # this before it gets here, but a stale/unvalidated run should still
    # not fail silently. See docs/BUGS.md BUG-0014.
    if release_type and release_type not in RELEASE_TYPES:
        detail = (
            f"unknown auto_update.release_type {release_type!r}, falling back "
            f"to default (semver-or-commit) resolution"
        )
        print(f"  warning: {pkg_name}: {detail}", file=sys.stderr)
        failures.append(Failure(pkg_name, "config", detail))

    # Default: try semver, fall back to commit
    print(f"fetching tags: {pkg_name} ...", file=sys.stderr)
    tags, fetch_error = fetch_tags(url)
    if fetch_error:
        failures.append(Failure(pkg_name, "tags", fetch_error))
        return
    latest = latest_semver(tags)
    if latest:
        pkg_to_latest[pkg_name] = latest.lstrip("v")
    elif ref is None:
        detail = "no semver tag and submodule not pulled, nothing to resolve"
        print(f"  warning: {pkg_name}: {detail}", file=sys.stderr)
        failures.append(Failure(pkg_name, "resolve", detail))
    else:
        commit_info = get_submodule_commit_with_base(repo, ref)
        if commit_info:
            pkg_to_commit_info[pkg_name] = commit_info


def render_failure_block(failures: "list[Failure]") -> list[str]:
    """#COPR-0004, #BUG-0100: render the aggregated failure report for stdout.

    Grouped by `kind` so a run with e.g. 8 unrelated "resolve" misses and one
    real "fetch" outage doesn't bury the outage in the noise. Returns an empty
    list when there's nothing to report -- callers decide whether that's worth
    printing at all.

    #BUG-0101: sorted by `scope` within each kind group -- `failures` is
    appended to from multiple worker threads under UPDATE_VERSIONS_JOBS>1, so
    append order is completion order, not something this (or the committed
    docs/nightly-summary.md sentinel below) can afford to depend on.
    """
    if not failures:
        return []
    lines = [f"{len(failures)} upstream refresh failure(s):"]
    by_kind: dict[str, list[Failure]] = {}
    for failure in failures:
        by_kind.setdefault(failure.kind, []).append(failure)
    for kind in sorted(by_kind):
        group = sorted(by_kind[kind], key=lambda f: f.scope)
        lines.append(f"  [{kind}] ({len(group)}):")
        for failure in group:
            lines.append(f"    {failure.scope}: {failure.detail}")
    return lines


def render_failure_markdown(failures: "list[Failure]") -> str:
    """#COPR-0004, #BUG-0100: render the durable Markdown sentinel body.

    Written to LOG_DIR/.update-versions-failures.md when failures is
    non-empty, and folded into docs/nightly-summary.md by
    scripts/pkg-log-analysis.py. Carries a timestamp so a stale leftover (one
    that scripts/pkg-log-analysis.py somehow reads without this run having
    removed it) is self-evidently not tonight's.
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "## Upstream version refresh",
        "",
        f"_Generated {now} by `make update-versions`._",
        "",
        f"{len(failures)} failure(s):",
        "",
    ]
    by_kind: dict[str, list[Failure]] = {}
    for failure in failures:
        by_kind.setdefault(failure.kind, []).append(failure)
    for kind in sorted(by_kind):
        lines.append(f"### {kind}")
        lines.append("")
        for failure in sorted(by_kind[kind], key=lambda f: f.scope):
            lines.append(f"- `{failure.scope}`: {failure.detail}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    if not GITMODULES.exists():
        print(f"error: {GITMODULES} not found", file=sys.stderr)
        sys.exit(1)

    modules = parse_gitmodules(GITMODULES)
    url_to_module = {mod["url"]: mod for mod in modules}

    # #BUG-0100: every warn-and-continue site below also appends here, so one
    # aggregated report can be rendered/persisted at the end of the run
    # instead of failures only ever scrolling past on stderr.
    failures: list[Failure] = []

    # Load packages.yaml. Config/versions below are keyed by PACKAGE NAME, not
    # url: multiple packages (e.g. Hyprland / Hyprland-git) can legitimately
    # point at the same submodule url but need independent release_type
    # handling. Keying by url let one package's config silently shadow
    # another's (see docs/BUGS.md).
    packages: dict = {}
    if PACKAGES_YAML.exists():
        # get_packages exits on error; ignore and continue
        with contextlib.suppress(SystemExit):
            packages = get_packages(PACKAGES_YAML)

    # One physical checkout per submodule url. Three things are derived per
    # url below:
    #  - branch: which branch moving (non-pinned) packages track
    #  - pin:    a pinned package's checkout target; a pin beats every moving
    #            sibling on the same url, which is only safe because version
    #            resolution further down reads origin/<branch>, never the
    #            working tree (see docs/BUGS.md BUG-0033)
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
            detail = (
                f"{pin.owner} pins this submodule to "
                f"{pin.candidates or '(unresolved)'} but {existing.owner} already "
                f"pinned it to {existing.candidates or '(unresolved)'}; keeping "
                f"{existing.owner}'s (first in packages.yaml)"
            )
            print(f"  warning: {url}: {detail}", file=sys.stderr)
            failures.append(Failure(url, "config", detail))

    # #BUG-0101: UPDATE_VERSIONS_JOBS=1 (or a single item either loop) runs
    # strictly serially -- the path every ordered-run_git-side_effect test in
    # tests/test_update_versions.py relies on. >1 spreads pull/fetch across a
    # thread pool: each iteration below writes only its own dict key
    # (url_to_ref[url], pkg_to_latest[pkg_name], pkg_to_commit_info[pkg_name]),
    # so concurrent writes from different threads never collide -- see
    # docs/features/COPR-0004-version-auto-bump.md.
    jobs = env_int("UPDATE_VERSIONS_JOBS", 8)

    print("pulling submodules ...", file=sys.stderr)
    url_to_ref: dict[str, str | None] = {}

    def _pull_one(mod: dict) -> None:
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
        url_to_ref[url] = pull_submodule(
            mod, branch=url_to_branch.get(url), pin=pin, failures=failures
        )

    _run_parallel(jobs, _pull_one, modules)

    pkg_to_latest: dict[str, str] = {}
    pkg_to_commit_info: dict[str, tuple[str, str, str, str | None]] = {}

    def _resolve_one(item: tuple[str, dict]) -> None:
        pkg_name, pkg_data = item
        _resolve_package_version(
            pkg_name,
            pkg_data,
            url_to_module,
            url_to_ref,
            pkg_to_latest,
            pkg_to_commit_info,
            failures,
        )

    _run_parallel(jobs, _resolve_one, list(packages.items()))

    # Print summary YAML to stdout
    summary = {}
    for pkg_name, pkg_data in packages.items():
        if pkg_name in pkg_to_latest:
            latest_str: str | None = pkg_to_latest[pkg_name]
        elif pkg_name in pkg_to_commit_info:
            _full_hash, short, date, base = pkg_to_commit_info[pkg_name]
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

    # #BUG-0100: the aggregated failure report -- everything collected above
    # was already printed live as it happened, one line at a time on stderr;
    # this is the single place a human (or docs/nightly-summary.md, via the
    # sentinel below) sees the whole run's damage at once.
    for line in render_failure_block(failures):
        print(line)

    # Sentinel files for `make update-daily`'s end-of-run summary line and for
    # scripts/pkg-log-analysis.py folding this run's failures into
    # docs/nightly-summary.md. Written/removed on every exit path (including
    # the early return below) so a stale leftover from a previous run can
    # never be read as tonight's -- see LOG_DIR / ".update-versions-count"
    # consumer in Makefile's update-daily target.
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    failures_sentinel = LOG_DIR / ".update-versions-failures.md"
    if failures:
        failures_sentinel.write_text(render_failure_markdown(failures))
    else:
        failures_sentinel.unlink(missing_ok=True)

    if not PACKAGES_YAML.exists():
        print(f"warning: {PACKAGES_YAML} not found, skipping update", file=sys.stderr)
        (LOG_DIR / ".update-versions-count").write_text("0\n")
        return

    changed = update_package_versions(PACKAGES_YAML, pkg_to_latest, pkg_to_commit_info)
    if changed:
        print("updated packages.yaml:", file=sys.stderr)
        for pkg, (old, new) in sorted(changed.items()):
            print(f"  {pkg}: {old} -> {new}", file=sys.stderr)
    else:
        print("packages.yaml: all versions already up to date", file=sys.stderr)

    (LOG_DIR / ".update-versions-count").write_text(f"{len(changed)}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
