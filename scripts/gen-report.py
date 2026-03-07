#!/usr/bin/env python3
"""Generate a Markdown README from build-report.yaml using a Jinja2 template."""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from lib.jinja_utils import create_jinja_env
from lib.paths import PACKAGES_YAML, ROOT
from lib.version import clean_version

REPORT_YAML = ROOT / "build-report.yaml"
COPR_BUILD_URL = "https://copr.fedorainfracloud.org/coprs/build/{}/"


def collect_packages(
    stages: dict,
    pkg_meta: dict,
    pkg_badge: dict,
) -> list[dict]:
    names: list[str] = []
    seen: set[str] = set()
    for stage_data in stages.values():
        for name in (stage_data or {}).keys():
            if name not in seen:
                names.append(name)
                seen.add(name)

    packages = []
    for name in names:
        spec = (stages.get("spec") or {}).get(name, {})
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
    result = subprocess.run(
        ["git", "log", "--format=%an|%ae"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    seen: set[str] = set()
    contributors = []
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=["github", "copr"],
        default="github",
        help="Output format: github (table) or copr (list)",
    )
    args = parser.parse_args()
    template_name = f"readme-{args.format}.md.j2"

    if not REPORT_YAML.exists():
        print(f"error: {REPORT_YAML} not found", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(REPORT_YAML.read_text())
    run = data.get("run", {})
    stages = data.get("stages", {})

    repo = {}
    pkg_meta = {}
    groups_cfg = {}
    badge_style = None
    if PACKAGES_YAML.exists():
        yaml_data = yaml.safe_load(PACKAGES_YAML.read_text())
        repo = yaml_data.get("repo", {})
        pkg_meta = yaml_data.get("packages", {})
        groups_cfg = yaml_data.get("groups", {})
        badge_style = repo.get("documents", {}).get("badge_style")

    pkg_badge: dict[str, dict] = {}
    for group_data in groups_cfg.values():
        if group_cfg_badge := group_data.get("badge"):
            for name in group_data.get("packages") or []:
                if isinstance(name, str):
                    pkg_badge[name] = group_cfg_badge

    packages = collect_packages(stages, pkg_meta, pkg_badge)
    pkg_by_name = {p["name"]: p for p in packages}
    groups = collect_groups(groups_cfg, pkg_by_name)
    contributors = collect_contributors(ROOT)

    env = create_jinja_env()
    template = env.get_template(template_name)
    print(
        template.render(
            run=run,
            repo=repo,
            packages=packages,
            groups=groups,
            contributors=contributors,
            badge_style=badge_style,
        ),
        end="",
    )


if __name__ == "__main__":
    main()
