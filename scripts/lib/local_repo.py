"""Helpers for the per-chroot dnf repo under local-repo/<target>/.

Shared by stage-mock.py (which fills it) and delete-package.py (which empties
it of one package's RPMs).
"""

import logging
import subprocess
from pathlib import Path

from lib import build_db
from lib.paths import LOCAL_REPO_ROOT


def rpm_query(rpm_path: Path, fmt: str) -> str:
    """Query a single field from an RPM file via rpm --queryformat."""
    result = subprocess.run(
        ["rpm", "-qp", "--queryformat", fmt, str(rpm_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def regenerate_repo_metadata(repo_dir: Path) -> None:
    """Regenerate repo_dir's repo metadata to index all packages built for
    that target. Creates repo_dir if this is the first build for it --
    createrepo_c errors on a nonexistent directory."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["createrepo_c", "--update", str(repo_dir)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        logging.error(
            "createrepo_c failed: %s",
            result.stderr.decode() if result.stderr else "",
        )
        raise RuntimeError(f"createrepo_c failed with code {result.returncode}")


def rpm_source_name(rpm_path: Path) -> str:
    """#COPR-0013, #BUG-0071: name of the source package an RPM was built from
    (`pkg` for `pkg-libs-1.0-1.fc44.x86_64.rpm` built from `pkg-1.0-1.fc44.src.rpm`).

    Empty string if the RPM can't be read. Matching on this, not on the file
    name prefix, keeps `hyprland` from claiming `hyprland-protocols`'s RPMs.
    """
    srpm = rpm_query(rpm_path, "%{SOURCERPM}")
    if not srpm.endswith(".src.rpm"):
        return ""
    # <name>-<version>-<release>.src.rpm
    parts = srpm[: -len(".src.rpm")].rsplit("-", 2)
    return parts[0] if len(parts) == 3 else ""


def remove_package_rpms(pkg: str, root: Path = LOCAL_REPO_ROOT) -> dict[str, int]:
    """#COPR-0013, #BUG-0071: unlink every RPM built from source package `pkg`
    out of each root/<target>/ dir, drop its artifacts-ledger row, and
    regenerate repo metadata for each target that lost something (otherwise
    dnf keeps indexing files that are gone). Returns {target: removed count}.
    """
    removed: dict[str, int] = {}
    if not root.is_dir():
        return removed
    for target_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        count = 0
        for rpm_path in sorted(target_dir.glob("*.rpm")):
            if rpm_path.name.endswith(".src.rpm"):
                continue
            if rpm_source_name(rpm_path) != pkg:
                continue
            rpm_path.unlink()
            build_db.delete_artifact("repo", str(rpm_path))
            count += 1
        if count:
            removed[target_dir.name] = count
            regenerate_repo_metadata(target_dir)
    return removed
