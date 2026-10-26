#!/usr/bin/env python3
"""Generate the Markdown READMEs from yaml, NEWS and git history using Jinja2 templates.

Reads no build-report.db and polls nothing: there is no markdown build report (#COPR-0012).
"""

import argparse
import sys
from pathlib import Path

from lib.jinja_utils import create_jinja_env
from lib.paths import GROUPS_YAML, PACKAGES_YAML, REPO_YAML, ROOT
from lib.readme_content import collect_contributors, get_recent_news, get_sections
from lib.yaml_utils import (
    get_packages,
    load_groups_yaml,
    load_repo_yaml,
)


def collect_groups(groups_cfg: dict, pkg_meta: dict) -> list[dict]:
    """#COPR-0012: build the README package list from groups.yaml + packages.yaml.

    A `packages:` entry is listed only if it exists in packages.yaml (its summary is
    shown); `packages_from_global_repo` entries are listed as given.
    """
    groups = []
    for key, group_data in groups_cfg.items():
        pkgs = [
            {"name": name, "summary": (pkg_meta[name] or {}).get("summary", "")}
            for name in (group_data.get("packages") or [])
            if name in pkg_meta
        ]
        # Add packages from global repo (external packages)
        for global_pkg in group_data.get("packages_from_global_repo") or []:
            if isinstance(global_pkg, dict):
                pkgs.append(
                    {
                        "name": global_pkg.get("name", ""),
                        "summary": global_pkg.get("summary", ""),
                    }
                )
        groups.append(
            {
                "label": group_data.get("label", key),
                "badge": group_data.get("badge"),
                "packages": pkgs,
            }
        )
    return groups


def main() -> None:
    """#COPR-0012: render the requested README templates from yaml/NEWS/git inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=["github", "copr"],
        action="append",
        dest="formats",
        help="Output format: github (table) or copr (list). "
        "Repeatable -- pair each with an --output to render several templates from "
        "one read of the inputs instead of one process per format "
        "(see docs/TODO.md TODO-0067). Defaults to a single 'github' render.",
    )
    parser.add_argument(
        "--output",
        type=str,
        action="append",
        dest="outputs",
        help="Output file path, one per --format in the same order. If omitted for "
        "a single-format call, writes to stdout.",
    )
    args = parser.parse_args()
    formats = args.formats or ["github"]
    outputs = args.outputs or [None] * len(formats)
    if len(outputs) != len(formats):
        parser.error("--output must be given once per --format (or not at all)")

    pkg_meta = get_packages() if PACKAGES_YAML.exists() else {}
    repo = load_repo_yaml() if REPO_YAML.exists() else {}
    groups_cfg = load_groups_yaml() if GROUPS_YAML.exists() else {}
    badge_style = repo.get("documents", {}).get("badge_style")

    groups = collect_groups(groups_cfg, pkg_meta)
    contributors = collect_contributors(ROOT)
    news_limit = repo.get("documents", {}).get("news_limit", 8)
    news_entries = get_recent_news(ROOT, limit=news_limit)
    sections = get_sections(repo)

    env = create_jinja_env()
    for fmt, out in zip(formats, outputs, strict=True):
        template = env.get_template(f"readme-{fmt}.md.j2")
        output = template.render(
            repo=repo,
            groups=groups,
            contributors=contributors,
            badge_style=badge_style,
            news_entries=news_entries,
            sections=sections,
        )

        if out:
            Path(out).write_text(output)
        else:
            print(output, end="")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
