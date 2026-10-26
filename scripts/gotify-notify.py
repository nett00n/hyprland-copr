#!/usr/bin/env python3
"""#COPR-0026: send a message, or tonight's update-daily summary, to Gotify.

Usage:
  gotify-notify.py --title T --message M [--priority N]
  gotify-notify.py --summary

Reads GOTIFY_URL (server base URL) and GOTIFY_TOKEN (application token) from the
environment (`make` exports them from .env). Unset config or a failed send is a
warning, never a non-zero exit: a down Gotify must not fail `make update-daily`.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from lib import build_db
from lib.paths import LOG_DIR

SUMMARY_TITLE = "hyprland-copr update-daily"
SEND_TIMEOUT = 10
PRIORITY_NORMAL = 5
PRIORITY_ERRORS = 8


def send(url: str, token: str, title: str, message: str, priority: int) -> bool:
    """#COPR-0026: POST one message; return False (after a warning) on any failure.

    The token travels in the X-Gotify-Key header, not the URL, so it never lands
    in a proxy/access log.
    """
    try:
        # Built inside the try: urllib raises ValueError here for a URL with no
        # scheme (e.g. GOTIFY_URL=gotify.example.org), which must stay a warning.
        req = urllib.request.Request(
            url.rstrip("/") + "/message",
            data=json.dumps(
                {"title": title, "message": message, "priority": priority}
            ).encode(),
            headers={"Content-Type": "application/json", "X-Gotify-Key": token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=SEND_TIMEOUT):
            return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"warning: gotify send failed: {exc}", file=sys.stderr)
        return False


def build_run_counts(since: int) -> tuple[int, int, list[str]]:
    """#COPR-0026: (checked, succeeded, failed package names) for runs started >= since."""
    conn = build_db.connect()
    states: dict[str, set[str]] = {}
    for table in ("stage_history", "stage_results"):
        rows = conn.execute(
            f"SELECT package, state FROM {table} WHERE run_id IN "
            "(SELECT id FROM runs WHERE started_at >= ?)",
            (since,),
        )
        for package, state in rows:
            states.setdefault(package, set()).add(state)
    errors = sorted(p for p, s in states.items() if "failed" in s)
    return len(states), len(states) - len(errors), errors


def format_summary(
    changes: dict[str, tuple[str, str]],
    checked: int,
    succeeded: int,
    errors: list[str],
) -> str:
    """#COPR-0026: `updated 3: foo 1.1.1>1.1.2, ... checked: 3, succeeded: 2, errors: bar`."""
    updated = f"updated {len(changes)}"
    if changes:
        updated += ": " + ", ".join(
            f"{pkg} {old}>{new}" for pkg, (old, new) in sorted(changes.items())
        )
    return (
        f"{updated}. checked: {checked}, succeeded: {succeeded}, "
        f"errors: {', '.join(errors) or 'none'}"
    )


def build_summary() -> tuple[str, int]:
    """#COPR-0026: (message, priority) from tonight's sentinels and build-report.db."""
    changes: dict[str, tuple[str, str]] = {}
    changes_path = LOG_DIR / ".update-versions-changes.json"
    if changes_path.exists():
        raw = json.loads(changes_path.read_text() or "{}")
        changes = {pkg: (old, new) for pkg, (old, new) in raw.items()}
    started_path = LOG_DIR / ".update-daily-started"
    since = int(started_path.read_text().strip()) if started_path.exists() else 0
    checked, succeeded, errors = build_run_counts(since)
    priority = PRIORITY_ERRORS if errors else PRIORITY_NORMAL
    return format_summary(changes, checked, succeeded, errors), priority


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--title", default="hyprland-copr")
    parser.add_argument("--message", default="")
    parser.add_argument("--priority", type=int, default=PRIORITY_NORMAL)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    url = os.environ.get("GOTIFY_URL", "")
    token = os.environ.get("GOTIFY_TOKEN", "")
    if not url or not token:
        print(
            "warning: GOTIFY_URL and GOTIFY_TOKEN must both be set; skipping notification",
            file=sys.stderr,
        )
        return 0

    if args.summary:
        title = SUMMARY_TITLE
        message, priority = build_summary()
    elif args.message:
        title, message, priority = args.title, args.message, args.priority
    else:
        parser.error("--message or --summary is required")

    if send(url, token, title, message, priority):
        print(f"gotify: sent '{title}'")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
