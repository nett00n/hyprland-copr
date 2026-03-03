"""Jinja2 environment factory."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .paths import TEMPLATE_DIR


def create_jinja_env(template_dir: Path | None = None) -> Environment:
    """Create and return a Jinja2 Environment with standard settings."""
    td = template_dir or TEMPLATE_DIR
    return Environment(
        loader=FileSystemLoader(str(td)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
