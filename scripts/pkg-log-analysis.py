#!/usr/bin/env python3
"""#COPR-0022: analyze build logs for a package and report actionable errors.

Usage:
  pkg-log-analysis.py <package> [<package> ...] [--run-id N] [--target T] [--output FILE]

Without --run-id/--target, each package's logs are resolved to the newest run
under logs/runs/ that has a directory for it (a matrix run can have more than
one target in that same run_id; every matching target is analyzed). --output
additionally writes a durable Markdown summary linking back to those exact
per-run, per-target log paths -- see docs/nightly-summary.md and
docs/features/COPR-0022-run-scoped-logs-and-summary.md.
"""

import argparse
import sys
from pathlib import Path

from lib.log_analysis import (
    _analyze_srpm_log,
    _analyze_mock_log,
    _analyze_mock_build_log,
    _analyze_mock_root_log,
    _analyze_copr_log,
    _analyze_copr_chroot_summary,
    _analyze_copr_chroot_logs,
    _suggest_providers,
)
from lib.paths import RUNS_LOG_DIR, get_package_log_dir

HIGHLIGHT_PREFIX = "█▓▒░"


def resolve_log_dirs(pkg: str, run_id: int | None, target: str | None) -> list[Path]:
    """#COPR-0022: resolve the log dir(s) to analyze for `pkg`.

    An explicit run_id+target pins one directory (returned whether or not it
    exists -- callers report "no logs" for a miss). Otherwise, find the
    newest run under logs/runs/ that has at least one target directory for
    this package, and return every such target within that run (a matrix
    night logs the same package once per chroot, in the same run_id).
    """
    if run_id is not None and target is not None:
        return [get_package_log_dir(pkg, run_id, target)]
    if not RUNS_LOG_DIR.exists():
        return []

    candidate_runs = sorted(
        (
            int(p.name)
            for p in RUNS_LOG_DIR.iterdir()
            if p.is_dir() and p.name.isdigit()
        ),
        reverse=True,
    )
    for candidate_run_id in candidate_runs:
        if run_id is not None and candidate_run_id != run_id:
            continue
        run_dir = RUNS_LOG_DIR / str(candidate_run_id)
        matches = sorted(
            d
            for d in run_dir.glob(f"*/{pkg}")
            if d.is_dir() and (target is None or d.parent.name == target)
        )
        if matches:
            return matches
    return []


def collect_issues(pkg: str, log_dir: Path) -> list[str]:
    """Return formatted issue lines for one package's log dir (empty if clean)."""
    lines: list[str] = []

    srpm_log = log_dir / "10-srpm.log"
    if srpm_log.exists():
        issues = _analyze_srpm_log(srpm_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} SRPM stage issues:")
            for lineno, _raw_line, msg, dep, method in issues:
                lines.append(f"  - {msg}")
                lines.append(f"    {srpm_log}:{lineno}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    lines.append(f"    suggested packages:\n      {yaml_list}")

    mock_log = log_dir / "20-mock.log"
    if mock_log.exists():
        issues = _analyze_mock_log(mock_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} Mock builddep issues:")
            for lineno, _raw_line, msg, dep, method in issues:
                lines.append(f"  - {msg}")
                lines.append(f"    {mock_log}:{lineno}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    lines.append(f"    suggested packages:\n      {yaml_list}")

    build_log = log_dir / "21-mock-build.log"
    if build_log.exists():
        issues = _analyze_mock_build_log(build_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} Mock build issues:")
            for lineno, raw_line, msg, dep, method in issues:
                lines.append(f"  - {msg}")
                lines.append(f"    {build_log}:{lineno}: {raw_line}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    lines.append(f"    suggested packages:\n      {yaml_list}")

    root_log = log_dir / "21-mock-root.log"
    if root_log.exists():
        issues = _analyze_mock_root_log(root_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} Mock root issues:")
            for lineno, raw_line, msg, _dep, _method in issues:
                lines.append(f"  - {msg}")
                lines.append(f"    {root_log}:{lineno}: {raw_line}")

    copr_log = log_dir / "30-copr.log"
    if copr_log.exists():
        issues = _analyze_copr_log(copr_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} COPR stage issues:")
            for lineno, _raw_line, msg, _dep, _method in issues:
                lines.append(f"  - {msg}")
                lines.append(f"    {copr_log}:{lineno}")

    chroot_summary_log = log_dir / "30-copr-chroots.log"
    if chroot_summary_log.exists():
        issues = _analyze_copr_chroot_summary(chroot_summary_log)
        if issues:
            lines.append(f"\n{HIGHLIGHT_PREFIX} COPR chroot mismatch:")
            for _lineno, _raw_line, msg, _dep, _method in issues:
                lines.append(f"  - {msg}")

    for chroot_name, issues in _analyze_copr_chroot_logs(log_dir).items():
        chroot_log = log_dir / f"31-copr-{chroot_name}.log"
        lines.append(f"\n{HIGHLIGHT_PREFIX} COPR builder issues ({chroot_name}):")
        for lineno, raw_line, msg, dep, method in issues:
            lines.append(f"  - {msg}")
            lines.append(f"    {chroot_log}:{lineno}: {raw_line}")
            providers = _suggest_providers(dep, method)
            if providers:
                yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                lines.append(f"    suggested packages:\n      {yaml_list}")

    return lines


def analyze_package(pkg: str, log_dir: Path) -> tuple[int, list[str]]:
    """Analyze one log dir for a package, printing what collect_issues finds.

    Returns (result, issue_lines): result is 0 clean, 1 issues found, 2 no
    logs; issue_lines is collect_issues()'s output (empty unless result == 1).
    """
    if not log_dir.exists():
        print(
            f"{HIGHLIGHT_PREFIX} ✗ Log directory not found: {log_dir}", file=sys.stderr
        )
        return 2, []

    lines = collect_issues(pkg, log_dir)
    if not lines:
        print(f"{HIGHLIGHT_PREFIX} ✓ No issues found in {pkg} logs")
        return 0, []

    for line in lines:
        print(line)
    return 1, lines


def render_markdown_summary(
    results: list[tuple[str, Path, int, list[str]]],
) -> str:
    """#COPR-0022: render a durable Markdown summary for --output.

    One section per (package, log_dir) analyzed, linking back to that exact
    run-scoped log directory so a failure found tonight can still be traced
    after `logs/` has moved on to later runs.
    """
    lines = ["# Nightly log analysis summary", ""]
    had_issues = any(result == 1 for _pkg, _log_dir, result, _issues in results)
    no_logs = [pkg for pkg, _d, result, _i in results if result == 2]
    clean = [pkg for pkg, _d, result, _i in results if result == 0]
    failing = [(pkg, d, i) for pkg, d, result, i in results if result == 1]

    lines.append(f"- Packages analyzed: {len(results)}")
    lines.append(f"- Clean: {len(clean)}")
    lines.append(f"- With issues: {len(failing)}")
    lines.append(f"- No logs found: {len(no_logs)}")
    lines.append("")

    if failing:
        lines.append("## Issues")
        lines.append("")
        for pkg, log_dir, issue_lines in failing:
            lines.append(f"### {pkg} (`{log_dir}`)")
            lines.append("")
            lines.append("```")
            lines.extend(line for line in issue_lines if line)
            lines.append("```")
            lines.append("")

    if no_logs:
        lines.append("## No logs found")
        lines.append("")
        for pkg in no_logs:
            lines.append(f"- {pkg}")
        lines.append("")

    return "\n".join(lines) + ("\n" if had_issues or no_logs else "")


def main(argv: list[str]) -> int:
    """#COPR-0022: analyze every package in argv in one process (instead of one
    process per package) so `make stage-log-analyze` doesn't spawn a
    container per package.

    A package with no log dir (analyze_package() -> 2) is just noted, not a
    failure -- that's the common case across the whole set and must not abort
    the rest. Returns 1 only if a package reported real issues.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="*")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--output", default=None, help="Write a Markdown summary here")
    args = parser.parse_args(argv)

    if not args.packages:
        print(f"Usage: {sys.argv[0]} <package> [<package> ...]")
        return 1

    had_issues = False
    summary_results: list[tuple[str, Path, int, list[str]]] = []

    for pkg in args.packages:
        log_dirs = resolve_log_dirs(pkg, args.run_id, args.target)
        if not log_dirs:
            print(f"{HIGHLIGHT_PREFIX} ⊘ No logs for {pkg}, skipping", file=sys.stderr)
            summary_results.append((pkg, Path("(none)"), 2, []))
            continue
        for log_dir in log_dirs:
            result, issue_lines = analyze_package(pkg, log_dir)
            if result == 1:
                had_issues = True
            summary_results.append((pkg, log_dir, result, issue_lines))

    if args.output:
        Path(args.output).write_text(render_markdown_summary(summary_results))
        print(f"{HIGHLIGHT_PREFIX} ✓ Wrote summary to {args.output}")

    return 1 if had_issues else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
