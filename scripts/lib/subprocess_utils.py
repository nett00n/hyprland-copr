"""Subprocess helpers for build scripts."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

_DEFAULT_TIMEOUT = 3600


def _cmd_timeout() -> int:
    """Return CMD_TIMEOUT from the environment, or the default if unset/invalid.

    A non-numeric value (e.g. "30s", or an empty CMD_TIMEOUT= inherited from
    .env) used to raise ValueError here, uncaught -- crashing the first
    run_cmd() of the run from inside a helper documented to return
    (ok, stdout, stderr) rather than raise.
    """
    raw = os.environ.get("CMD_TIMEOUT")
    if not raw:
        return _DEFAULT_TIMEOUT
    try:
        return int(raw)
    except ValueError:
        print(
            f"warning: CMD_TIMEOUT={raw!r} is not a valid integer, "
            f"falling back to {_DEFAULT_TIMEOUT}s",
            file=sys.stderr,
        )
        return _DEFAULT_TIMEOUT


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
        timeout = _cmd_timeout()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
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
    """Run a git command, returning the CompletedProcess. Never raises.

    Args:
        *args: git command arguments
        cwd: Working directory for git command
        timeout: Timeout in seconds (default 300 -- callers doing network work,
            e.g. `fetch`/`ls-remote`, should pass a shorter one, e.g. 30; callers
            doing local-only work, e.g. `rev-list`/`describe`, may tighten to 10)

    Returns:
        A CompletedProcess with returncode, stdout, stderr -- always, even on
        failure. A missing `git` binary or a timeout is reported the same way
        run_cmd() reports them, as a synthetic CompletedProcess rather than a
        raised exception:
          - git not found: returncode=127, stderr="command not found: git"
          - timed out: returncode=124, stderr="command timed out after {timeout}s: ..."
        Both cases leave stdout="". Callers should check returncode rather than
        wrap this call in try/except.
    """
    cmd = ["git", *args]
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "command not found: git")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            cmd, 124, "", f"command timed out after {timeout}s: {shlex.join(cmd)}"
        )
