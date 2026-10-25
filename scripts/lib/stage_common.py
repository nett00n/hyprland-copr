"""Helpers shared by the stage-*.py scripts."""

from lib import build_db
from lib.reporting import event


def record_config_skip(
    stage: str, pkg: str, target: str, run_id: int | None, fedora_version: str
) -> None:
    """#COPR-0002: record that `pkg` is skipped for this stage by packages.yaml config.

    Prints the stage event line and writes the `skipped` stage row (reason
    "config: skip"), for a package whose resolved metadata carries `_skip`
    (e.g. a `fedora:NN` skip override).
    """
    event(stage, target, pkg, "skip", reason=f"fedora:{fedora_version} skip")
    build_db.set_stage(pkg, stage, target, run_id, "skipped", reason="config: skip")
