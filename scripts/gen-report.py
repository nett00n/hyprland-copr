#!/usr/bin/env python3
"""Generate a Markdown build-status table from build-report.yaml using a Jinja2 template."""

import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
REPORT_YAML = ROOT / "build-report.yaml"
TEMPLATE_DIR = ROOT / "templates"
TEMPLATE_NAME = "build-report.md.j2"

COPR_BUILD_URL = "https://copr.fedorainfracloud.org/coprs/build/{}/"
BADGE_URL = "https://img.shields.io/badge/{label}-{message}-{color}"

STATE_COLOR = {
    "success": "brightgreen",
    "failed": "red",
    "skipped": "lightgrey",
}


def badge(label: str, state: str | None, url: str | None = None) -> str:
    state = state or "unknown"
    color = STATE_COLOR.get(state, "orange")
    img_url = BADGE_URL.format(label=label, message=state, color=color)
    img = f"![{label}]({img_url})"
    if url:
        return f"[{img}]({url})"
    return img


def clean_version(raw: str) -> str:
    """Strip -%autorelease.fcXX or -1.fcXX suffix, keep bare version number."""
    return raw.split("-")[0] if raw else ""


def collect_packages(stages: dict) -> list[dict]:
    # Union of all package names across all stages, in first-seen order
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

        # Pick version from the first stage that has one
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
                "spec_badge": badge("spec", spec.get("state")),
                "srpm_badge": badge("srpm", srpm.get("state")),
                "mock_badge": badge("mock", mock.get("state")),
                "copr_badge": badge("copr", copr.get("state"), copr_url),
            }
        )
    return packages


def main() -> None:
    if not REPORT_YAML.exists():
        print(f"error: {REPORT_YAML} not found", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(REPORT_YAML.read_text())
    run = data.get("run", {})
    stages = data.get("stages", {})

    packages = collect_packages(stages)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)), keep_trailing_newline=True
    )
    template = env.get_template(TEMPLATE_NAME)
    print(template.render(run=run, packages=packages), end="")


if __name__ == "__main__":
    main()
