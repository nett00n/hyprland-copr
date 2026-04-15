#!/usr/bin/env python3
"""Generate a Markdown README from build-report.yaml using a Jinja2 template."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib.copr import COPR_BUILD_URL, poll_copr_status
from lib.jinja_utils import create_jinja_env
from lib.paths import BUILD_STATUS_YAML, GROUPS_YAML, PACKAGES_YAML, REPO_YAML, ROOT
from lib.subprocess_utils import run_git
from lib.version import clean_version
from lib.yaml_utils import (
    get_packages,
    load_groups_yaml,
    load_repo_yaml,
    save_build_status,
)


def _format_duration(
    started_at: int | None, completed_at: int | None, fallback_at: int | None = None
) -> str:
    """Format duration between started_at and completed_at as human-readable string.

    If completed_at is missing but fallback_at is provided, uses fallback_at instead.
    This allows tracking execution time for failed steps using an alternative timestamp.
    """
    # Use completed_at if available, otherwise try fallback_at
    end_time = completed_at or fallback_at
    if not started_at or not end_time:
        return ""

    duration_secs = end_time - started_at
    if duration_secs < 0:
        return ""  # Invalid if end time is before start time
    if duration_secs < 60:
        return f"{duration_secs}s"
    minutes = duration_secs // 60
    seconds = duration_secs % 60
    if minutes < 60:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _format_date(started_at: int | None) -> str:
    """Format started_at timestamp as human-readable date string."""
    if not started_at:
        return ""
    dt = datetime.fromtimestamp(started_at, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def collect_packages(
    stages: dict,
    pkg_meta: dict,
    pkg_badge: dict,
    run_completed_at: int | None = None,
) -> list[dict]:
    """Collect packages from build status stages.

    Extracts relevant fields for markdown report generation.
    Note: hashes are cached metadata and not included in markdown output.
    Duration calculated from started_at and completed_at timestamps.
    For failed/incomplete steps, uses run_completed_at as fallback timestamp.
    """
    names: list[str] = []
    seen: set[str] = set()
    for stage_data in stages.values():
        for name in (stage_data or {}).keys():
            if name not in seen:
                names.append(name)
                seen.add(name)

    packages = []
    for name in names:
        validate = (stages.get("validate") or {}).get(name, {})
        spec = (stages.get("spec") or {}).get(name, {})
        vendor = (stages.get("vendor") or {}).get(name, {})
        srpm = (stages.get("srpm") or {}).get(name, {})
        mock = (stages.get("mock") or {}).get(name, {})
        copr = (stages.get("copr") or {}).get(name, {})

        copr_build_id = copr.get("build_id")
        copr_url = COPR_BUILD_URL.format(copr_build_id) if copr_build_id else None

        raw_version = (
            spec.get("version")
            or srpm.get("version")
            or mock.get("version")
            or copr.get("version")
            or ""
        )

        packages.append(
            {
                "name": name,
                "version": clean_version(raw_version),
                "summary": (pkg_meta.get(name) or {}).get("summary", ""),
                "badge": pkg_badge.get(name),
                "mock_state": mock.get("state"),
                "copr_state": copr.get("state"),
                "copr_url": copr_url,
                "stages": {
                    "validate": {
                        "state": validate.get("state"),
                        "errors": validate.get("errors", 0),
                        "warnings": validate.get("warnings", 0),
                    },
                    "spec": {
                        "state": spec.get("state"),
                        "date": _format_date(spec.get("started_at")),
                        "duration": _format_duration(
                            spec.get("started_at"),
                            spec.get("completed_at"),
                            run_completed_at,
                        ),
                        "reason": spec.get("reason"),
                    },
                    "vendor": {
                        "state": vendor.get("state"),
                        "date": _format_date(vendor.get("started_at")),
                        "duration": _format_duration(
                            vendor.get("started_at"),
                            vendor.get("completed_at"),
                            run_completed_at,
                        ),
                        "reason": vendor.get("reason"),
                    },
                    "srpm": {
                        "state": srpm.get("state"),
                        "date": _format_date(srpm.get("started_at")),
                        "duration": _format_duration(
                            srpm.get("started_at"),
                            srpm.get("completed_at"),
                            run_completed_at,
                        ),
                        "reason": srpm.get("reason"),
                    },
                    "mock": {
                        "state": mock.get("state"),
                        "date": _format_date(mock.get("started_at")),
                        "duration": _format_duration(
                            mock.get("started_at"),
                            mock.get("completed_at"),
                            run_completed_at,
                        ),
                        "reason": mock.get("reason"),
                    },
                    "copr": {
                        "state": copr.get("state"),
                        "date": _format_date(copr.get("started_at")),
                        "duration": _format_duration(
                            copr.get("started_at"),
                            copr.get("completed_at"),
                            run_completed_at,
                        ),
                        "reason": copr.get("reason"),
                    },
                },
            }
        )
    return packages


def collect_groups(groups_cfg: dict, pkg_by_name: dict) -> list[dict]:
    groups = []
    for _key, group_data in groups_cfg.items():
        pkgs = [
            pkg_by_name[name]
            for name in (group_data.get("packages") or [])
            if name in pkg_by_name
        ]
        # Add packages from global repo (external packages)
        for global_pkg in group_data.get("packages_from_global_repo") or []:
            if isinstance(global_pkg, dict):
                pkgs.append(
                    {
                        "name": global_pkg.get("name", ""),
                        "summary": global_pkg.get("summary", ""),
                        "version": None,
                        "badge": None,
                        "mock_state": None,
                        "copr_state": None,
                        "copr_url": None,
                    }
                )
        groups.append(
            {
                "label": group_data.get("label", _key),
                "badge": group_data.get("badge"),
                "packages": pkgs,
            }
        )
    return groups


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


def get_latest_blog(repo_root: Path) -> str:
    """Get the latest blog post from ./blog/ directory."""
    blog_dir = repo_root / "blog"
    if not blog_dir.exists():
        return ""

    blog_files = sorted(blog_dir.glob("*.md"), reverse=True)
    if not blog_files:
        return ""

    return blog_files[0].read_text()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=["github", "copr", "full-report"],
        default="github",
        help="Output format: github (table), copr (list), or full-report (detailed)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not provided, writes to stdout.",
    )
    parser.add_argument(
        "--skip-copr-poll",
        action="store_true",
        help="Skip polling COPR status updates (use cached status from build-report.yaml).",
    )
    args = parser.parse_args()
    template_name = (
        f"readme-{args.format}.md.j2"
        if args.format != "full-report"
        else "full-report.md.j2"
    )

    if not BUILD_STATUS_YAML.exists():
        print(f"error: {BUILD_STATUS_YAML} not found", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(BUILD_STATUS_YAML.read_text())
    run = data.get("run", {})
    stages = data.get("stages", {})

    # Poll COPR status for packages with non-terminal states (unless skipped)
    if not args.skip_copr_poll:
        copr_stage = stages.get("copr") or {}
        packages_list = list(copr_stage.keys())
        if poll_copr_status(stages, packages_list):
            # Status was updated, save it back
            data["stages"] = stages
            save_build_status(data)

    pkg_meta = get_packages() if PACKAGES_YAML.exists() else {}
    repo = load_repo_yaml() if REPO_YAML.exists() else {}
    groups_cfg = load_groups_yaml() if GROUPS_YAML.exists() else {}
    badge_style = repo.get("documents", {}).get("badge_style")

    pkg_badge: dict[str, dict] = {}
    for group_data in groups_cfg.values():
        if group_cfg_badge := group_data.get("badge"):
            for name in group_data.get("packages") or []:
                if isinstance(name, str):
                    pkg_badge[name] = group_cfg_badge

    packages = collect_packages(stages, pkg_meta, pkg_badge, run.get("completed_at"))
    pkg_by_name = {p["name"]: p for p in packages}
    groups = collect_groups(groups_cfg, pkg_by_name)
    contributors = collect_contributors(ROOT)
    latest_blog = get_latest_blog(ROOT)

    env = create_jinja_env()
    template = env.get_template(template_name)
    output = template.render(
        run=run,
        repo=repo,
        packages=packages,
        groups=groups,
        contributors=contributors,
        badge_style=badge_style,
        latest_blog=latest_blog,
    )

    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
