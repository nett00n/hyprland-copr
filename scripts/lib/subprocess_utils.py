"""Subprocess helpers for build scripts."""

import subprocess
from pathlib import Path


def run_cmd(cmd: str, log_path: Path | None = None) -> tuple[bool, str, str]:
    """Run a shell command, optionally appending output to log_path.

    Returns (ok, stdout, stderr).
    """
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if log_path:
        with open(log_path, "a") as fh:
            fh.write(f"$ {cmd}\n")
            if result.stdout:
                fh.write(result.stdout)
            if result.stderr:
                fh.write(result.stderr)
            fh.write(f"[exit: {result.returncode}]\n\n")
    return result.returncode == 0, result.stdout, result.stderr


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a git command, returning the CompletedProcess."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
