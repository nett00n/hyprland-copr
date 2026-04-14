"""Build summary printing and badge generation."""

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


def verbose_proceed_check(stage_checked: str, pkg: str, state: str | None) -> bool:
    """Print PROCEED_BUILD check result. Returns True if stage should be skipped."""
    skip = state == "success"
    action = "skip" if skip else ("retry" if state == "failed" else "run")
    print(f"  [CHECK] {stage_checked}: {pkg} — prior={state or 'none'} → {action}")
    return skip


def status(stage: str, pkg: str, result: str, detail: str = "") -> None:
    """Print a single-line stage status line."""
    tag = {"ok": "[OK]  ", "fail": "[FAIL]", "skip": "[SKIP]"}[result]
    suffix = f" — {detail}" if detail else ""
    print(f"  {tag} {stage}: {pkg}{suffix}")


def print_summary(packages: dict, report: dict, copr_repo: str) -> None:
    """Print the final build summary table."""
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
            pkg_data = report.get("stages", {}).get(stage, {}).get(pkg, {})
            state = pkg_data.get("state", "-")
            reason = pkg_data.get("reason", "")
            # Show "cached" if stage was cached, otherwise show state
            if reason == "cached":
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
            cell = f"{icon}({ts})" if ts and state == "skipped" else icon
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
