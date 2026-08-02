#!/usr/bin/env python3
"""Regenerate only the branding shell (logo/description/news/docs/support/license/
people) of generated docs, leaving the packages/build-status body untouched.

Unlike gen-report.py, this needs no build-report.db -- only repo.yaml, blog/NEWS.md,
and git log. Meant for environments with no build history (CI): see
docs/operations.md "CI docs-shell publish" for why gen-report.py can't run there.

Splices the rendered `__header.j2`/`__footer.j2` into the existing file between
their `<!-- BEGIN: X -->`/`<!-- END: X -->` markers; everything between the header
and footer (the packages table, build status) is left exactly as committed.
"""

import re
import sys

from lib.jinja_utils import create_jinja_env
from lib.paths import REPO_YAML, ROOT
from lib.readme_content import collect_contributors, get_recent_news, get_sections
from lib.yaml_utils import load_repo_yaml

TARGETS = ["README.md", "docs/README.copr.md"]

HEADER_RE = re.compile(r"<!-- BEGIN: Header -->.*?<!-- END: Header -->", re.DOTALL)
FOOTER_RE = re.compile(r"<!-- BEGIN: Footer -->.*?<!-- END: Footer -->", re.DOTALL)


def main() -> None:
    if not REPO_YAML.exists():
        print("repo.yaml not found, nothing to do", file=sys.stderr)
        sys.exit(1)
    repo = load_repo_yaml()

    context = {
        "repo": repo,
        "contributors": collect_contributors(ROOT),
        "news_entries": get_recent_news(
            ROOT, limit=repo.get("documents", {}).get("news_limit", 8)
        ),
        "sections": get_sections(repo),
    }

    env = create_jinja_env()
    header = env.get_template("__header.j2").render(**context).strip()
    footer = env.get_template("__footer.j2").render(**context).strip()

    changed = []
    for rel_path in TARGETS:
        path = ROOT / rel_path
        if not path.exists():
            print(f"skip (missing): {rel_path}", file=sys.stderr)
            continue

        text = path.read_text()
        if not HEADER_RE.search(text) or not FOOTER_RE.search(text):
            print(f"skip (no BEGIN/END markers found): {rel_path}", file=sys.stderr)
            continue

        new_text = HEADER_RE.sub(lambda _m: header, text, count=1)
        new_text = FOOTER_RE.sub(lambda _m: footer, new_text, count=1)

        if new_text != text:
            path.write_text(new_text)
            changed.append(rel_path)
            print(f"updated: {rel_path}")
        else:
            print(f"unchanged: {rel_path}")

    if not changed:
        print("Nothing changed.")


if __name__ == "__main__":
    main()
