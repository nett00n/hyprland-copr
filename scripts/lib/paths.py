"""Canonical path constants for the hyprland-copr repository."""

from pathlib import Path

# scripts/lib/ -> scripts/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGES_YAML = ROOT / "packages.yaml"
GITMODULES = ROOT / ".gitmodules"
LOG_DIR = ROOT / "logs"
LOCAL_REPO = ROOT / "local-repo"
TEMPLATE_DIR = ROOT / "templates"
