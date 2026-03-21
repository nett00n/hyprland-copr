#!/usr/bin/env python3
"""Analyze build logs for a package and report actionable errors."""

import sys
from pathlib import Path

# Add parent directory to path for imports (E402 ok: path setup before imports)
sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from scripts.lib.log_analysis import (  # noqa: E402
    _analyze_srpm_log,
    _analyze_mock_log,
    _analyze_mock_build_log,
    _suggest_providers,
)

HIGHLIGHT_PREFIX = "█▓▒░"


def analyze_package(pkg: str) -> int:
    """Analyze logs for a package. Returns 0 if issues found, 1 if no logs."""
    log_dir = Path("logs/build") / pkg
    if not log_dir.exists():
        print(f"{HIGHLIGHT_PREFIX} ✗ Log directory not found: {log_dir}")
        return 1

    issues_found = False

    # SRPM stage
    srpm_log = log_dir / "10-srpm.log"
    if srpm_log.exists():
        issues = _analyze_srpm_log(srpm_log)
        if issues:
            issues_found = True
            print(f"\n{HIGHLIGHT_PREFIX} SRPM stage issues:")
            for lineno, raw_line, msg, dep, method in issues:
                print(f"  - {msg}")
                print(f"    {srpm_log}:{lineno}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    print(f"    suggested packages:\n      {yaml_list}")

    # Mock stage (builddep)
    mock_log = log_dir / "20-mock.log"
    if mock_log.exists():
        issues = _analyze_mock_log(mock_log)
        if issues:
            issues_found = True
            print(f"\n{HIGHLIGHT_PREFIX} Mock builddep issues:")
            for lineno, raw_line, msg, dep, method in issues:
                print(f"  - {msg}")
                print(f"    {mock_log}:{lineno}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    print(f"    suggested packages:\n      {yaml_list}")

    # Mock stage (build)
    build_log = log_dir / "21-mock-build.log"
    if build_log.exists():
        issues = _analyze_mock_build_log(build_log)
        if issues:
            issues_found = True
            print(f"\n{HIGHLIGHT_PREFIX} Mock build issues:")
            for lineno, raw_line, msg, dep, method in issues:
                print(f"  - {msg}")
                print(f"    {build_log}:{lineno}: {raw_line}")
                providers = _suggest_providers(dep, method)
                if providers:
                    yaml_list = "\n      ".join(f'- "{p}"' for p in providers)
                    print(f"    suggested packages:\n      {yaml_list}")

    if not issues_found:
        print(f"{HIGHLIGHT_PREFIX} ✓ No issues found in {pkg} logs")
        return 0

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <package>")
        sys.exit(1)

    pkg = sys.argv[1]
    sys.exit(analyze_package(pkg))
