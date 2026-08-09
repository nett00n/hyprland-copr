"""Configuration utilities.

Provides functions for loading and resolving configuration values.

Environment variables:
  CMD_TIMEOUT     Command timeout in seconds (default 3600/60min). Used by run_cmd() in subprocess_utils.py.
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR, CRITICAL.
  PACKAGER        Packager name/email for RPM headers (format: "Name <email@example.com>").

See also env_flag() below for the shared boolean-flag parser used by other scripts' own
env vars (e.g. FORCE_REBUILD in full-cycle.py/stage-show-plan.py).
"""

import logging
import os
import subprocess
import sys
from pathlib import Path


def env_flag(name: str) -> bool:
    """True when env var `name` is set to 1/true/yes (case-insensitive).

    Most boolean flags in this codebase are read inline as
    `os.environ.get("X", "").lower() == "true"`, which rejects the `1` a user
    naturally types on a `make FOO=1` command line. Use this helper for new
    flags instead of adding another inline variant.
    """
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def get_packager() -> str:
    """Resolve packager name/email from environment, config file, or git.

    Tries sources in order of priority (highest to lowest):
    1. PACKAGER environment variable
    2. PACKAGER_NAME and PACKAGER_EMAIL environment variables
    3. .env file (PACKAGER, PACKAGER_NAME, PACKAGER_EMAIL keys)
    4. git config user.name and user.email
    5. Default fallback

    Returns:
        String in format "Name <email@example.com>"
    """
    # 1. Try environment variables (highest priority)
    packager = os.environ.get("PACKAGER")
    if packager:
        return packager

    env_var_name = os.environ.get("PACKAGER_NAME", "").strip()
    env_var_email = os.environ.get("PACKAGER_EMAIL", "").strip()
    if env_var_name and env_var_email:
        return f"{env_var_name} <{env_var_email}>"

    # 2. Try .env file
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        env_name: str = ""
        env_email: str = ""
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("PACKAGER="):
                    return line.split("=", 1)[1].strip().strip("\"'")
                elif line.startswith("PACKAGER_NAME="):
                    env_name = line.split("=", 1)[1].strip().strip("\"'")
                elif line.startswith("PACKAGER_EMAIL="):
                    env_email = line.split("=", 1)[1].strip().strip("\"'")
        if env_name and env_email:
            return f"{env_name} <{env_email}>"

    # 3. Try gitconfig (lowest priority)
    try:
        git_name = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
        git_email = subprocess.check_output(
            ["git", "config", "user.email"], text=True
        ).strip()
        if git_name and git_email:
            return f"{git_name} <{git_email}>"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 4. Default fallback
    return "Packager <packager@example.com>"


def setup_logging() -> None:
    """Configure Python logging module from LOG_LEVEL env var.

    Supports LOG_LEVEL=DEBUG, INFO (default), WARNING, ERROR, CRITICAL.
    All output goes to stderr with format: "LEVEL: message".

    Machine-readable output (YAML, spec content, etc.) should use print()
    to stdout separately — logging is for diagnostic messages only.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    fmt = "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stderr)
