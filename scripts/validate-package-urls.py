#!/usr/bin/env python3
"""Validate that package URLs in packages.yaml match .gitmodules.

Exits with status 0 if all URLs match, 1 if there are mismatches.
"""

import re
import sys
import yaml
from pathlib import Path


def parse_gitmodules(path: Path) -> dict[str, str]:
    """Parse .gitmodules and return {submodule_name: url} dict."""
    gitmodules_map = {}
    with open(path) as f:
        content = f.read()
        for match in re.finditer(
            r'\[submodule "([^"]+)"\].*?url\s*=\s*(.+?)(?=\n\[|$)',
            content,
            re.DOTALL,
        ):
            name = match.group(1)
            url = match.group(2).strip()
            gitmodules_map[name] = url
    return gitmodules_map


def get_package_from_submodule(submodule_name: str) -> str:
    """Extract package name from submodule name (e.g., 'submodules/org/pkg' -> 'pkg')."""
    return submodule_name.split("/")[-1]


def main() -> int:
    root = Path(__file__).parent.parent

    # Parse .gitmodules
    gitmodules_path = root / ".gitmodules"
    if not gitmodules_path.exists():
        print("error: .gitmodules not found", file=sys.stderr)
        return 1

    gitmodules_map = parse_gitmodules(gitmodules_path)

    # Load packages.yaml
    packages_path = root / "packages.yaml"
    if not packages_path.exists():
        print("error: packages.yaml not found", file=sys.stderr)
        return 1

    try:
        packages = yaml.safe_load(packages_path.read_text())
    except yaml.YAMLError as e:
        print(f"error: failed to parse packages.yaml: {e}", file=sys.stderr)
        return 1

    # Check for mismatches and format issues
    mismatches = []
    format_errors = []
    for pkg_name in packages.keys():
        pkg_data = packages[pkg_name]
        pkg_url = pkg_data.get("url", "").strip()

        # Check URL format: must be https://, not git@
        if pkg_url and pkg_url.startswith("git@"):
            format_errors.append(
                (
                    pkg_name,
                    pkg_url,
                    "URL must be in https:// format, not git@",
                )
            )

        # Find matching submodule
        matching_submodule = None
        for submodule_name in gitmodules_map.keys():
            if get_package_from_submodule(submodule_name) == pkg_name:
                matching_submodule = submodule_name
                break

        if matching_submodule:
            gitmodules_url = gitmodules_map[matching_submodule].strip()
            # URLs can differ only by .git suffix (needed for git operations but breaks tarball downloads)
            pkg_url_normalized = pkg_url.removesuffix(".git")
            gitmodules_url_normalized = gitmodules_url.removesuffix(".git")
            if pkg_url_normalized != gitmodules_url_normalized:
                mismatches.append((pkg_name, pkg_url, gitmodules_url))

    # Report results
    if format_errors:
        print(
            "error: package URLs must be in https:// format, not git@:",
            file=sys.stderr,
        )
        for pkg_name, pkg_url, reason in format_errors:
            print(f"  {pkg_name}: {pkg_url}", file=sys.stderr)
            print(f"    {reason}", file=sys.stderr)
        return 1

    if mismatches:
        print(
            "error: package URLs in packages.yaml do not match .gitmodules:",
            file=sys.stderr,
        )
        for pkg_name, pkg_url, gitmodules_url in mismatches:
            print(f"  {pkg_name}:", file=sys.stderr)
            print(f"    packages.yaml: {pkg_url}", file=sys.stderr)
            print(f"    .gitmodules:   {gitmodules_url}", file=sys.stderr)
        return 1

    print("✓ All package URLs match .gitmodules and are in correct format")
    return 0


if __name__ == "__main__":
    sys.exit(main())
