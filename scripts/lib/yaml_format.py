"""YAML formatting utilities.

Provides shared helpers for formatting YAML files, including:
- ruamel.yaml support for literal block style (|)
- Yamllint configuration parsing
- Indentation detection
"""

import sys

import yaml

from lib.paths import ROOT
from lib.yaml_config import FORMAT_FILE


def dump_yaml_literal(data: dict, indent: int = 2, explicit_start: bool = False) -> str:
    """Dump data as YAML with multi-line strings in block (|) style.

    Args:
        data: Dictionary to serialize
        indent: Indentation level (default 2)
        explicit_start: Add document start marker (---) if True

    Returns:
        YAML string with literal blocks for multi-line values
    """
    config = FORMAT_FILE(indent, explicit_start)
    return config.dump(data)


def load_yamllint_config() -> dict:
    """Load and parse .yamllint configuration file.

    Returns:
        Dictionary with configuration from .yamllint, or empty dict if not found
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

        # Use literal dumper to preserve pipe notation (|) for multi-line strings
        formatted = dump_yaml_literal(
            data,
            indent=indent_spaces,
            explicit_start=explicit_start,
        )

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
