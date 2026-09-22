#!/usr/bin/env python3
"""#BUG-0039, #COPR-0007: bound-retry-poll Copr until every build this run
submitted reaches a terminal state, before docs are rendered.

`stage-copr.py` submits with `--nowait` (async), so a package resubmitted
tonight starts as Copr state `unknown` in build-report.db. `make readme` used
to poll once, seconds later -- almost always too early for a build that just
started. This script polls repeatedly (see lib.copr.poll_copr_status's
`deadline_s`/`interval_s`) so `make readme`, run right after, renders each
package's real state instead.

A build still non-terminal when the deadline elapses is left as `unknown` --
it resolves on the *next* run's existing pre-submit poll
(full-cycle.py's poll_copr_status() call before resubmitting). That is not a
nightly failure, so this script always exits 0.

Environment variables:
  PACKAGE            Restrict polling to these packages (optional, comma-separated)
  FEDORA_VERSION     Fedora version to target (default: 44)
  MOCK_CHROOT        Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_POLL_TIMEOUT  Total seconds to keep retrying (default: 1800; 0 = one pass)
  COPR_POLL_INTERVAL Seconds between retry passes (default: 30)
  LOG_LEVEL          Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import sys

from lib import build_db
from lib.config import env_int, setup_logging
from lib.copr import TERMINAL_STATES, poll_copr_status
from lib.paths import resolve_target


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "44")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)

    package_filter = {
        p.strip() for p in os.environ.get("PACKAGE", "").split(",") if p.strip()
    }

    copr_stage = build_db.stage_map(target, stage="copr").get("copr", {})
    packages = sorted(copr_stage) if not package_filter else sorted(package_filter)

    timeout = env_int("COPR_POLL_TIMEOUT", 1800)
    interval = env_int("COPR_POLL_INTERVAL", 30)

    pending_before = {
        pkg
        for pkg in packages
        if copr_stage.get(pkg, {}).get("build_id")
        and copr_stage.get(pkg, {}).get("state") not in TERMINAL_STATES
    }

    if not pending_before:
        print(f"copr-wait: nothing to wait for on {target} (0 pending builds)")
        return

    print(
        f"copr-wait: waiting on {len(pending_before)} pending build(s) on {target} "
        f"(timeout={timeout}s, interval={interval}s)"
    )
    poll_copr_status(target, packages, deadline_s=timeout, interval_s=interval)

    final_stage = build_db.stage_map(target, stage="copr").get("copr", {})
    still_pending = {
        pkg
        for pkg in pending_before
        if final_stage.get(pkg, {}).get("state") not in TERMINAL_STATES
    }
    resolved = len(pending_before) - len(still_pending)
    print(f"copr-wait: {resolved} of {len(pending_before)} resolved")
    if still_pending:
        print(
            "copr-wait: still building at deadline, will resolve on the next run: "
            + ", ".join(sorted(still_pending))
        )


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
