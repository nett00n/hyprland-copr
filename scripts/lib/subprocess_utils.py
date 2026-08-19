"""Subprocess helpers for build scripts."""

import os
import shlex
import subprocess
from pathlib import Path


def run_cmd(
    cmd: list[str],
    log_path: Path | None = None,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> tuple[bool, str, str]:
    """Run a command, optionally appending output to log_path.

    Args:
        cmd: Command and arguments
        log_path: Optional path to append output to
        timeout: Timeout in seconds (default 3600/60min, override via CMD_TIMEOUT env var)
        cwd: Working directory to run the command in

    Returns (ok, stdout, stderr).
    """
    if timeout is None:
        timeout = int(os.environ.get("CMD_TIMEOUT", 3600))
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "", f"command timed out after {timeout}s: {shlex.join(cmd)}"
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as fh:
            fh.write(f"$ {shlex.join(cmd)}\n")
            if result.stdout:
                fh.write(result.stdout)
            if result.stderr:
                fh.write(result.stderr)
            fh.write(f"[exit: {result.returncode}]\n\n")
    return result.returncode == 0, result.stdout, result.stderr


def run_git(
    *args: str, cwd: Path | None = None, timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run a git command, returning the CompletedProcess.

    Args:
        *args: git command arguments
        cwd: Working directory for git command
        timeout: Timeout in seconds (default 300)

    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )
