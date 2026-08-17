"""Build summary printing, per-event logging, and badge generation."""

import os
import sys
from datetime import datetime

STATE_COLOR = {
    "success": "brightgreen",
    "failed": "red",
    "skipped": "lightgrey",
}

STATUS_EMOJI = {
    "success": "✔",
    "failed": "✘",
    "skipped": "○",
}

BADGE_URL = "https://img.shields.io/badge/{label}-{message}-{color}"

# ANSI colors for the `state=` value only -- the rest of the line stays plain
# so redirected output/log files and grep never have to deal with escape codes.
_STATE_ANSI = {
    "RUN": "\033[33m",  # yellow
    "OK": "\033[32m",  # green
    "FAIL": "\033[31m",  # red
    "SKIP": "\033[90m",  # grey
    "CHECK": "\033[36m",  # cyan
}
# ANSI colors for the `stage=` value, one per pipeline stage -- lets you spot
# "which stage is this line about" at a glance while scanning a scrolling log,
# independent of (and visually distinct from) the state colors above.
_STAGE_ANSI = {
    "validate": "\033[34m",  # blue
    "spec": "\033[35m",  # magenta
    "vendor": "\033[36m",  # cyan
    "srpm": "\033[94m",  # bright blue
    "mock": "\033[95m",  # bright magenta
    "copr": "\033[96m",  # bright cyan
}
_ANSI_RESET = "\033[0m"


def _color_enabled() -> bool:
    return not os.environ.get("NO_COLOR") and sys.stdout.isatty()


def event(stage: str, target: str, pkg: str, state: str, **fields: str) -> None:
    """Print a single tab-separated, RFC3339-timestamped event line.

    Format: `<rfc3339 ts>\\tstage=<stage>\\ttarget=<target>\\tpkg=<pkg>\\tstate=<STATE>`,
    followed by any non-empty `key=value` extras. See docs/operations.md "Stage event
    lines".
    """
    state = state.upper()
    stage_display = stage
    if _color_enabled():
        if state in _STATE_ANSI:
            state = f"{_STATE_ANSI[state]}{state}{_ANSI_RESET}"
        if stage in _STAGE_ANSI:
            stage_display = f"{_STAGE_ANSI[stage]}{stage}{_ANSI_RESET}"
    parts = [
        datetime.now().astimezone().isoformat(timespec="seconds"),
        f"stage={stage_display}",
        f"target={target}",
        f"pkg={pkg}",
        f"state={state}",
    ]
    for key, value in fields.items():
        if value:
            parts.append(f"{key}={value}")
    print("\t".join(parts), flush=True)


def verbose_proceed_check(
    stage_checked: str, pkg: str, state: str | None, target: str
) -> bool:
    """Print PROCEED_BUILD check result. Returns True if stage should be skipped."""
    skip = state == "success"
    action = "skip" if skip else ("retry" if state == "failed" else "run")
    event(stage_checked, target, pkg, "CHECK", prior=state or "none", action=action)
    return skip


def status(stage: str, pkg: str, result: str, target: str, detail: str = "") -> None:
    """Print a single-line stage event."""
    state = {"ok": "ok", "fail": "fail", "skip": "skip"}[result]
    event(stage, target, pkg, state, reason=detail)


def print_summary(packages: dict, stages: dict, copr_repo: str) -> None:
    """Print the final build summary table.

    `stages` is the {stage: {package: entry}} shape returned by
    lib.build_db.stage_map(target).
    """
    if not packages:
        print("\nNo packages to summarize.")
        return

    stage_keys = ["validate", "spec", "vendor", "srpm", "mock"] + (
        ["copr"] if copr_repo else []
    )
    col_w = max(len(p) for p in packages) + 2
    header = f"{'package':<{col_w}}" + "".join(f"{s:<18}" for s in stage_keys)
    sep = "-" * len(header)
    print(f"\nSummary:\n{sep}\n{header}\n{sep}")
    for pkg in packages:
        row = f"{pkg:<{col_w}}"
        for stage in stage_keys:
            pkg_data = stages.get(stage, {}).get(pkg, {})
            state = pkg_data.get("state", "-")
            reason = pkg_data.get("reason", "")
            # "not-vendored": this package has no vendor stage at all (not
            # Go/Rust) -- show "n/a", not "cached" (a real cache hit) or a
            # bare "SKIP(ts)" (which reads like a build step that was
            # deliberately bypassed). See docs/bugs.md, formerly BUG-0045.
            if reason == "not-vendored":
                icon = "n/a"
            elif reason == "cached":
                # Show "cached" if stage was cached, otherwise show state
                icon = "cached"
            else:
                # Validate uses WARN for failures (warning level), other stages use FAIL
                if stage == "validate":
                    icon = {"success": "OK", "failed": "WARN", "skipped": "SKIP"}.get(
                        state, state
                    )
                else:
                    icon = {"success": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(
                        state, state
                    )
            ts = pkg_data.get("completed_at")
            show_ts = state == "skipped" and reason != "not-vendored"
            cell = f"{icon}({ts})" if ts and show_ts else icon
            row += f"{cell:<18}"
        print(row)
    print(sep)


def badge_short(
    label: str, state: str | None, url: str | None = None, style: str | None = None
) -> str:
    """Generate a shields.io badge with a label, emoji message, and status-colored background."""
    from urllib.parse import quote

    state = state or "unknown"
    color = STATE_COLOR.get(state, "orange")
    emoji = STATUS_EMOJI.get(state, "?")
    img_url = f"https://img.shields.io/badge/{label}-{quote(emoji)}-{color}"
    if style:
        img_url += f"?style={style}"
    img = f"![{label}:{state}]({img_url})"
    if url:
        return f"[{img}]({url})"
    return img


def badge(
    label: str, state: str | None, url: str | None = None, style: str | None = None
) -> str:
    """Generate a shields.io badge markdown string."""
    state = state or "unknown"
    color = STATE_COLOR.get(state, "orange")
    img_url = BADGE_URL.format(label=label, message=state, color=color)
    if style:
        img_url += f"?style={style}"
    img = f"![{label}]({img_url})"
    if url:
        return f"[{img}]({url})"
    return img
