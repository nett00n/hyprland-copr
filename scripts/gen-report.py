#!/usr/bin/env python3
"""Generate a Markdown build-status table from build-report.yaml using a Jinja2 template."""

import subprocess
import sys
from pathlib import Path

import yaml

from lib.jinja_utils import create_jinja_env
from lib.paths import PACKAGES_YAML, ROOT
from lib.reporting import badge
from lib.version import clean_version

REPORT_YAML = ROOT / "build-report.yaml"
TEMPLATE_NAME = "build-report.md.j2"

COPR_BUILD_URL = "https://copr.fedorainfracloud.org/coprs/build/{}/"


def collect_packages(stages: dict, pkg_meta: dict) -> list[dict]:
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
                "spec_badge": badge("spec", spec.get("state")),
                "srpm_badge": badge("srpm", srpm.get("state")),
                "mock_badge": badge("mock", mock.get("state")),
                "copr_badge": badge("copr", copr.get("state"), copr_url),
            }
        )
    return packages


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
    if not REPORT_YAML.exists():
        print(f"error: {REPORT_YAML} not found", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(REPORT_YAML.read_text())
    run = data.get("run", {})
    stages = data.get("stages", {})

    pkg_meta = {}
    if PACKAGES_YAML.exists():
        pkg_meta = yaml.safe_load(PACKAGES_YAML.read_text()).get("packages", {})

    packages = collect_packages(stages, pkg_meta)
    contributors = collect_contributors(ROOT)

    env = create_jinja_env()
    template = env.get_template(TEMPLATE_NAME)
    print(
        template.render(run=run, packages=packages, contributors=contributors), end=""
    )


if __name__ == "__main__":
    main()
