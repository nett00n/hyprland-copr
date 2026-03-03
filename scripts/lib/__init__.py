"""Shared utilities for hyprland-copr build scripts.

Import guards: fails fast with a helpful message if PyYAML or Jinja2
are missing, so callers don't get cryptic ImportError tracebacks.
"""

import sys

try:
    import yaml  # noqa: F401
except ImportError:
    sys.exit("error: PyYAML not installed — run: make setup-venv")

try:
    from jinja2 import Environment  # noqa: F401
except ImportError:
    sys.exit("error: Jinja2 not installed — run: make setup-venv")
