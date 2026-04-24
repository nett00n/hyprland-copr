#!/usr/bin/env python3
"""Format YAML files following .yamllint rules.

Usage:
    python3 scripts/format-yaml.py '*.yaml'  # Format all YAML files matching pattern
"""

import argparse
import glob
import sys
from pathlib import Path

import yaml
from lib.paths import ROOT
from lib.yaml_config import FORMAT_FILE


def load_yamllint_config() -> dict:
    """Load and parse .yamllint configuration file.

    Returns:
        Dictionary with configuration from .yamllint
    """
    yamllint_config = ROOT / ".yamllint"
    if not yamllint_config.exists():
        return {}

    try:
        with open(yamllint_config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        print(f"Warning: Could not parse .yamllint: {e}", file=sys.stderr)
        return {}


def get_ignored_files(config: dict) -> set[str]:
    """Parse ignored files from .yamllint config.

    Args:
        config: Parsed .yamllint configuration

    Returns:
        Set of filenames to ignore
    """
    ignored: set[str] = set()
    if not config or "ignore" not in config:
        return ignored

    try:
        ignore_str = config["ignore"]
        # Parse the ignore block (each line is a filename)
        for line in ignore_str.strip().split("\n"):
            line = line.strip()
            if line:
                ignored.add(line)
    except Exception as e:
        print(f"Warning: Could not parse ignore rules: {e}", file=sys.stderr)

    return ignored


def get_formatting_rules(config: dict) -> dict:
    """Extract formatting rules from yamllint config.

    Args:
        config: Parsed .yamllint configuration

    Returns:
        Dictionary with formatting rules for yaml.dump()
    """
    rules = config.get("rules", {})

    # Extract indentation spacing
    # yamllint defaults to 4 spaces if not specified
    indentation = rules.get("indentation", {})
    if isinstance(indentation, str):
        indent_spaces = 4  # yamllint default
    elif isinstance(indentation, dict):
        spaces_value = indentation.get("spaces", 4)
        if spaces_value == "auto":
            indent_spaces = 4  # yamllint default when auto
        else:
            indent_spaces = spaces_value
    else:
        indent_spaces = 4  # yamllint default

    # Document start rule: add '---' if enabled
    doc_start = rules.get("document-start", {})
    explicit_start = False
    if isinstance(doc_start, dict):
        explicit_start = doc_start.get("level") is not None

    return {
        "indent_spaces": indent_spaces,
        "explicit_start": explicit_start,
    }


def detect_indentation(content: str) -> int:
    """Detect indentation level from YAML content.

    Args:
        content: YAML file content

    Returns:
        Indentation level (2 or 4, default 2)
    """
    for line in content.split("\n"):
        # Skip empty lines and document markers
        if not line or line.startswith("-"):
            continue
        # Count leading spaces
        spaces = len(line) - len(line.lstrip(" "))
        # Check for valid indentation (2 or 4 spaces typically)
        if spaces > 0 and spaces % 2 == 0:
            return spaces
    return 2


def format_yaml_file(filepath: str, formatting_rules: dict) -> bool:
    """Format a single YAML file and write it back.

    Args:
        filepath: Path to the YAML file
        formatting_rules: Dictionary with formatting rules

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse YAML
        data = yaml.safe_load(content)
        if data is None:
            # Empty file or only comments/whitespace
            return True

        # Detect indentation from original file (preserve existing style)
        indent_spaces = detect_indentation(content)
        explicit_start = formatting_rules.get("explicit_start", False)

        # Format using configured YAML serializer
        config = FORMAT_FILE(indent_spaces, explicit_start)
        formatted = config.dump(data)

        # Ensure trailing newline (new-line-at-end-of-file rule)
        if formatted and not formatted.endswith("\n"):
            formatted += "\n"

        # Remove trailing spaces on each line (trailing-spaces rule)
        lines = formatted.split("\n")
        formatted = "\n".join(line.rstrip() for line in lines)
        if not formatted.endswith("\n"):
            formatted += "\n"

        # Write back to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(formatted)

        return True
    except Exception as e:
        print(f"Error formatting {filepath}: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Format YAML files following .yamllint rules"
    )
    parser.add_argument("pattern", help="Glob pattern for YAML files (e.g., '*.yaml')")
    args = parser.parse_args()

    # Find matching files
    files = glob.glob(args.pattern)
    if not files:
        print(f"No files matching pattern: {args.pattern}", file=sys.stderr)
        return 1

    # Load .yamllint config
    yamllint_config = load_yamllint_config()
    formatting_rules = get_formatting_rules(yamllint_config)
    ignored = get_ignored_files(yamllint_config)

    # Filter out ignored files
    files_to_format = [f for f in files if Path(f).name not in ignored]

    # Format each file
    failed = []
    for filepath in sorted(files_to_format):
        if not format_yaml_file(filepath, formatting_rules):
            failed.append(filepath)

    # Report results
    if failed:
        print(f"Failed to format {len(failed)} file(s):", file=sys.stderr)
        for f in failed:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"Formatted {len(files_to_format)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
