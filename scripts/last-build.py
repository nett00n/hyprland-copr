#!/usr/bin/env python3
"""#COPR-0028: print last night's build stats and failure details (read-only).

Usage:
  last-build.py [--package P] [--target T] [--hours N] [--format text|md]

"Last night" is every run that started within --hours (default 12) before the
newest run's start. Each (package, stage, target) is resolved to its newest
stage_history row in that window, so a failure fixed by a later run isn't listed.
See docs/features/COPR-0028-last-build-stats.md.
"""

import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import build_db
from lib.log_analysis import (
    _analyze_copr_log,
    _analyze_mock_build_log,
    _analyze_mock_log,
    _analyze_mock_root_log,
    _analyze_srpm_log,
)
from lib.paths import ROOT

DEFAULT_HOURS = 12
SLOWEST_COUNT = 10
EXCERPT_MAX_LINES = 20
ERROR_LINE_RE = re.compile(r"error|fail", re.IGNORECASE)

# stage -> [(log file name, analyzer)] searched, in order, for the failure excerpt.
_STAGE_ANALYZERS = {
    "srpm": [("10-srpm.log", _analyze_srpm_log)],
    "mock": [
        ("20-mock.log", _analyze_mock_log),
        ("21-mock-build.log", _analyze_mock_build_log),
        ("21-mock-root.log", _analyze_mock_root_log),
    ],
    "copr": [("30-copr.log", _analyze_copr_log)],
}


def night_runs(hours: int) -> list[dict[str, Any]]:
    """#COPR-0028: runs started within `hours` before the newest run, oldest first."""
    conn = build_db.connect()
    newest = conn.execute("SELECT MAX(started_at) FROM runs").fetchone()[0]
    if newest is None:
        return []
    rows = conn.execute(
        "SELECT * FROM runs WHERE started_at >= ? ORDER BY started_at, id",
        (newest - hours * 3600,),
    ).fetchall()
    return [dict(r) for r in rows]


def latest_rows(run_ids: list[int]) -> list[dict[str, Any]]:
    """#COPR-0028: newest stage_history row per (package, stage, target) in `run_ids`."""
    if not run_ids:
        return []
    marks = ",".join("?" * len(run_ids))
    rows = build_db.connect().execute(
        f"SELECT * FROM stage_history WHERE run_id IN ({marks}) ORDER BY run_id",
        run_ids,
    )
    newest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        newest[(row["package"], row["stage"], row["target"])] = dict(row)
    return list(newest.values())


def stage_counts(rows: list[dict[str, Any]]) -> dict[tuple[str, str], Counter[str]]:
    """#COPR-0028: {(target, stage): Counter(state)}."""
    counts: dict[tuple[str, str], Counter[str]] = {}
    for r in rows:
        counts.setdefault((r["target"], r["stage"]), Counter())[r["state"]] += 1
    return counts


def _duration(row: dict[str, Any]) -> int:
    if row["started_at"] is None or row["completed_at"] is None:
        return 0
    return max(0, row["completed_at"] - row["started_at"])


def slowest(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """#COPR-0028: the `count` longest stages by completed_at - started_at."""
    return sorted(rows, key=_duration, reverse=True)[:count]


def _log_path(log: str) -> Path:
    path = Path(log)
    return path if path.is_absolute() else ROOT / path


def failure_excerpt(row: dict[str, Any]) -> tuple[list[str], str]:
    """#COPR-0028: (<=20 excerpt lines, link) for one failed stage row.

    The link is the log file holding the first analyzer issue as `path:line`, or the
    stage's own log when nothing was recognised. A missing log yields `log pruned`.
    """
    log = row.get("log") or ""
    if not log or not _log_path(log).exists():
        return [f"log pruned: {log or '(no log recorded)'}"], log
    log_dir = os.path.dirname(log)
    lines: list[str] = []
    link = ""
    for name, analyzer in _STAGE_ANALYZERS.get(row["stage"], []):
        candidate = os.path.join(log_dir, name)
        for lineno, _raw, msg, _dep, _method in analyzer(_log_path(candidate)):
            link = link or f"{candidate}:{lineno}"
            lines.append(msg)
    if lines:
        return lines[:EXCERPT_MAX_LINES], link
    text = _log_path(log).read_text(errors="replace").splitlines()
    errors = [line.strip() for line in text if ERROR_LINE_RE.search(line)]
    return (errors or text)[-EXCERPT_MAX_LINES:], log


def _when(epoch: int | None) -> str:
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else "-"


def _fmt_secs(secs: int) -> str:
    mins, s = divmod(secs, 60)
    return f"{mins}m{s:02d}s" if mins else f"{s}s"


def render(hours: int, package: str | None, target: str | None, fmt: str) -> str:
    """#COPR-0028: the full report as text or Markdown."""
    runs = [r for r in night_runs(hours) if target in (None, r["target"])]
    if not runs:
        return "no runs found\n"
    rows = [
        r
        for r in latest_rows([r["id"] for r in runs])
        if package in (None, r["package"])
    ]
    md = fmt == "md"
    out = [
        f"# Last night ({_when(runs[0]['started_at'])} - {_when(runs[-1]['started_at'])})\n"
    ]

    out.append("## Runs\n")
    for r in runs:
        duration = (
            _fmt_secs(r["completed_at"] - r["started_at"]) if r["completed_at"] else "-"
        )
        out.append(
            f"- run {r['id']} {r['target']} {r['exit_state'] or 'running'} "
            f"{_when(r['started_at'])} {duration}"
            + (f" filter={r['package_filter']}" if r["package_filter"] else "")
        )

    out.append("\n## Stage counts\n")
    for (tgt, stage), counter in sorted(stage_counts(rows).items()):
        states = ", ".join(f"{n} {s}" for s, n in sorted(counter.items()))
        out.append(f"- {tgt} {stage}: {states}")

    out.append("\n## Slowest stages\n")
    for r in slowest(rows, SLOWEST_COUNT):
        out.append(
            f"- {r['package']} {r['stage']} {r['target']}: {_fmt_secs(_duration(r))}"
        )

    # #COPR-0029: builds that fixed (or gave up fixing) their own dependencies.
    healed = sorted(
        (r for r in rows if str(r["reason"] or "").startswith("autoheal:")),
        key=lambda r: (r["package"], r["target"], r["stage"]),
    )
    if healed:
        out.append(f"\n## Autohealed ({len(healed)})\n")
        for r in healed:
            out.append(
                f"- {r['package']} {r['stage']} {r['target']} "
                f"{r['state']}: {r['reason']}"
            )

    failed = sorted(
        (r for r in rows if r["state"] == "failed"),
        key=lambda r: (r["package"], r["target"], r["stage"]),
    )
    out.append(f"\n## Failures ({len(failed)})\n")
    for r in failed:
        out.append(
            f"### {r['package']} {r['stage']} {r['target']} "
            f"(version {r['version'] or '-'}, reason {r['reason'] or '-'}, "
            f"build {r['build_id'] or '-'})\n"
        )
        excerpt, link = failure_excerpt(r)
        out.extend(f"    {line}" for line in excerpt)
        path = link.rsplit(":", 1)[0] if link.rsplit(":", 1)[-1].isdigit() else link
        out.append(f"\n  log: [{link}]({path})" if md else f"\n  log: {link}")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package")
    parser.add_argument("--target")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    parser.add_argument("--format", choices=("text", "md"), default="text")
    args = parser.parse_args(argv)
    print(
        render(args.hours, args.package or None, args.target or None, args.format),
        end="",
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
