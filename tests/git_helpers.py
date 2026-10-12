"""Tiny git helper shared by tests that build real local repos."""

import subprocess


def git(*args, cwd):
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
