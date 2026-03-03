"""Build summary printing and badge generation."""

STATE_COLOR = {
    "success": "brightgreen",
    "failed": "red",
    "skipped": "lightgrey",
}

BADGE_URL = "https://img.shields.io/badge/{label}-{message}-{color}"


def status(stage: str, pkg: str, result: str) -> None:
    """Print a single-line stage status line."""
    tag = {"ok": "[OK]  ", "fail": "[FAIL]", "skip": "[SKIP]"}[result]
    print(f"  {tag} {stage}: {pkg}")


def print_summary(packages: dict, report: dict, copr_repo: str) -> None:
    """Print the final build summary table."""
    stage_keys = ["spec", "srpm", "mock"] + (["copr"] if copr_repo else [])
    col_w = max(len(p) for p in packages) + 2
    header = f"{'package':<{col_w}}" + "".join(f"{s:<10}" for s in stage_keys)
    sep = "-" * len(header)
    print(f"\nSummary:\n{sep}\n{header}\n{sep}")
    for pkg in packages:
        row = f"{pkg:<{col_w}}"
        for stage in stage_keys:
            state = report["stages"][stage].get(pkg, {}).get("state", "-")
            icon = {"success": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(
                state, state
            )
            row += f"{icon:<10}"
        print(row)
    print(sep)


def badge(label: str, state: str | None, url: str | None = None) -> str:
    """Generate a shields.io badge markdown string."""
    state = state or "unknown"
    color = STATE_COLOR.get(state, "orange")
    img_url = BADGE_URL.format(label=label, message=state, color=color)
    img = f"![{label}]({img_url})"
    if url:
        return f"[{img}]({url})"
    return img
