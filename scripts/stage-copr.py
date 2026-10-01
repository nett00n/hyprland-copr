#!/usr/bin/env python3
"""Stage 4: Submit SRPMs to Copr and record build IDs.

Reads packages.yaml and build-report.db for srpm stage results.
Skips packages where srpm stage failed or COPR_REPO is not set.
Records build IDs in build-report.db.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE              Build only this package (optional, comma-separated)
  FEDORA_VERSION       Fedora version to target (default: 44)
  MOCK_CHROOT          Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  COPR_REPO            Copr repo slug, e.g. nett00n/hyprland (required)
  SKIP_PACKAGES        Skip these packages (optional, comma-separated)
  PROCEED_BUILD        Skip packages where copr stage already succeeded
  SYNCHRONOUS_COPR_BUILD  If 'true', wait for build completion (default: async with --nowait)
  REQUIRE_CHROOT_COVERAGE  If 'true', abort instead of warning when a Copr chroot has no
                          verified local mock build for a package being submitted (see
                          docs/BUGS.md BUG-0018). Default: warn and submit anyway.
  COPR_BATCH_DEPS       If 'false', submit every package independently instead of
                        chaining a package behind its same-run dependencies via
                        Copr build batches (`--after-build-id`). Default: true.
                        See docs/features/COPR-0007-copr-submission.md.
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from lib import build_db
from lib.config import env_flag, setup_logging
from lib.copr import (
    blackout_chroots,
    block_transitive_dependents,
    fetch_failed_chroot_logs,
    ineligible_packages,
    parse_build_id,
    preflight,
    print_chroot_coverage,
    resolve_batch_chain,
)
from lib.log_retention import refresh_latest_link
from lib.paths import (
    ARCH,
    CANONICAL_FEDORA_VERSION,
    DISTRO,
    ROOT,
    get_package_log_dir,
    get_run_log_dir,
    mock_chroot,
    resolve_target,
)
from lib.reporting import event, status, verbose_proceed_check
from lib.subprocess_utils import run_cmd
from lib.version import nvr
from lib.yaml_utils import apply_os_overrides, prepare_stage


def run_for_package(
    pkg: str,
    meta: dict,
    fedora_version: str,
    copr_repo: str,
    proceed: bool,
    target: str,
    run_id: int,
    synchronous: bool = False,
    after_build_id: int | None = None,
) -> bool:
    """#COPR-0007, #BUG-0107. Submit SRPM to Copr for a single package.

    Returns True on success/skip, False on a genuine build failure.

    Writes the copr stage row for `pkg`.

    If synchronous=False (default), uses --nowait flag for async submission.
    A synchronous watch that hits run_cmd()'s CMD_TIMEOUT is treated as a
    still-pending submission ("unknown" state), not a build failure.

    `after_build_id`, when given, is passed to `copr-cli build` as
    `--after-build-id` so Copr holds this submission in the next build batch
    behind the named build -- see `lib.copr.resolve_batch_chain()`, which
    callers use to resolve it from this run's own dependency graph.
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        event("copr", target, pkg, "skip", reason=f"fedora:{fedora_version} skip")
        build_db.set_stage(
            pkg, "copr", target, run_id, "skipped", reason="config: skip"
        )
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    has_devel = 1 if "devel" in meta else 0
    pkg_log_dir = get_package_log_dir(pkg, run_id, target)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "30-copr.log"
    log.unlink(missing_ok=True)

    # Skip if copr stage already succeeded
    copr_entry = build_db.get_stage(pkg, "copr", target)
    prior_copr_state = copr_entry.get("state") if copr_entry else None
    if proceed and verbose_proceed_check("copr", pkg, prior_copr_state, target):
        status("copr", pkg, "skip", target, "already succeeded", version=ver)
        return True

    # The SRPM being submitted is always the canonical target's (docs/FRD.md
    # COPR-0018: one spec, one SRPM, shared across every target via the
    # rpmbuild volume) -- not necessarily this run's own `target`/
    # FEDORA_VERSION, which for a standalone `make stage-copr` after a matrix
    # run is often just the default. Its own mock success is checked at that
    # same canonical target for the same reason: cross-chroot coverage is
    # already `main()`'s job (ineligible_packages()/copr_blocked_packages()),
    # so this is purely "does the SRPM we're about to submit actually exist
    # and come from a build that succeeded," not a second coverage check.
    canonical_target = mock_chroot(CANONICAL_FEDORA_VERSION)
    srpm_entry = build_db.get_stage(pkg, "srpm", canonical_target)
    mock_entry = build_db.get_stage(pkg, "mock", canonical_target)
    srpm_state = srpm_entry.get("state", "") if srpm_entry else ""
    srpm_path = srpm_entry.get("path") if srpm_entry else None
    mock_state = mock_entry.get("state", "") if mock_entry else ""
    # A recorded-but-vanished SRPM must never be submitted to Copr as-is -- see
    # docs/BUGS.md BUG-0015 (this stage was the publish-a-stale-SRPM vector).
    srpm_missing = bool(srpm_path) and not Path(str(srpm_path)).exists()

    if (
        srpm_state in ("failed", "skipped")
        or not srpm_path
        or srpm_missing
        or mock_state in ("failed", "skipped")
    ):
        blocker = (
            f"mock {mock_state}"
            if mock_state in ("failed", "skipped")
            else "srpm artifact missing"
            if srpm_missing
            else (
                f"srpm not built at canonical {canonical_target} "
                f"(run make full-cycle PACKAGE={pkg} "
                f"FEDORA_VERSION={CANONICAL_FEDORA_VERSION} SKIP_COPR=1, "
                "or make full-cycle-matrix)"
            )
            if srpm_entry is None
            else f"srpm {srpm_state}"
        )
        status("copr", pkg, "skip", target, blocker, version=ver)
        build_db.set_stage(
            pkg,
            "copr",
            target,
            run_id,
            "skipped",
            version=ver,
            reason=blocker,
            has_devel=has_devel,
        )
        return True

    event("copr", target, pkg, "run", ver=ver)
    cmd = ["copr-cli", "build"]
    if not synchronous:
        cmd.append("--nowait")
    if after_build_id is not None:
        cmd.extend(["--after-build-id", str(after_build_id)])
    cmd.extend([copr_repo, srpm_path])
    ok, stdout, stderr = run_cmd(cmd, log)

    # copr-cli prints "Created builds: N" as soon as the build is submitted,
    # before it starts watching/waiting -- so a build_id can exist even when
    # the overall command later fails (synchronous mode watched the build to
    # a "failed" terminal state, or run_cmd's own CMD_TIMEOUT killed the watch
    # -- #BUG-0107, and #BUG-0106 makes run_cmd() preserve that partial
    # stdout for a killed command). Parse it unconditionally so a failed or
    # killed watch still gets a build_id recorded, which fetch_failed_chroot_logs
    # and the "unknown" state below (via poll_copr_status) both need.
    build_id = parse_build_id(stdout)

    # A synchronous watch killed by CMD_TIMEOUT is not a build failure: the
    # submission already succeeded (that's how we have a build_id) and the
    # build is still running on Copr. Recording it as terminal "failed" with
    # no build_id (the old behavior) permanently stranded the row --
    # poll_copr_status() (lib/copr.py) only resumes polling a row that has a
    # build_id *and* a non-terminal state. #BUG-0107: treat a watch timeout
    # like an async submission -- "unknown", resolved later by `copr-wait` or
    # the next run's pre-submit poll -- and report success, since the
    # submission itself did succeed (docs/features/COPR-0007-copr-submission.md).
    timed_out = not ok and "timed out" in stderr
    if timed_out:
        ok = True

    # In async mode, or a synchronous watch that timed out (see above):
    # successful submission → "unknown" state (build pending/still running).
    # In sync mode that actually watched to a terminal state: "success"/"failed".
    state = (
        "unknown" if (not synchronous or timed_out) else ("success" if ok else "failed")
    )

    status("copr", pkg, "ok" if ok else "fail", target, version=ver)

    if not ok and synchronous and build_id:
        fetch_failed_chroot_logs(pkg, build_id, target, run_id)

    # #BUG-0107: a failed/timed-out row must carry why -- `reason` used to be
    # dropped on the floor here, leaving every such row NULL in the DB and the
    # rendered docs.
    reason = None
    if timed_out:
        reason = (
            f"copr watch timed out; build {build_id} still running on Copr"
            if build_id
            else "copr watch timed out before a build id was seen"
        )
    elif not ok:
        # Prefer stderr's last line (copr-cli's own errors go there); a build
        # that submitted fine but was watched to a "failed" terminal state
        # leaves stderr empty, so fall back to stdout's last non-blank line
        # (copr-cli prints the terminal "... Build N: failed" line there).
        tail = stderr.strip() or stdout.strip()
        reason = tail.splitlines()[-1] if tail else "copr-cli exited non-zero"

    extra: dict[str, Any] = {}
    if ok and synchronous and not timed_out:
        extra["completed_at"] = build_db.now_epoch()
    build_db.set_stage(
        pkg,
        "copr",
        target,
        run_id,
        state,
        version=ver,
        build_id=build_id,
        log=str(log.relative_to(ROOT)),
        has_devel=has_devel,
        reason=reason,
        **extra,
    )

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "44")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)
    copr_repo = os.environ.get("COPR_REPO", "")

    if not copr_repo:
        print(
            "error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)",
            file=sys.stderr,
        )
        sys.exit(2)
    if not preflight(copr_repo):
        sys.exit(2)

    proceed = env_flag("PROCEED_BUILD")
    synchronous = env_flag("SYNCHRONOUS_COPR_BUILD")

    run_id = build_db.start_run(
        target,
        DISTRO,
        fedora_version,
        ARCH,
        copr_repo=copr_repo,
        package_filter=os.environ.get("PACKAGE", ""),
    )
    # #COPR-0022: a standalone `make stage-copr` opens its own run, separate
    # from full-cycle.py's -- without this, `logs/runs/latest` kept pointing
    # at the last full-cycle-matrix run even after a newer stage-copr run
    # existed (the run humans most want to inspect after a nightly, since
    # it's the one that talks to Copr).
    get_run_log_dir(run_id, target).mkdir(parents=True, exist_ok=True)
    refresh_latest_link(run_id)

    all_packages, packages = prepare_stage("copr", target, proceed, include_all=True)

    require_coverage = env_flag("REQUIRE_CHROOT_COVERAGE")
    covered = print_chroot_coverage(copr_repo, packages)
    if not covered and require_coverage:
        print(
            "error: REQUIRE_CHROOT_COVERAGE=true and some chroots lack a "
            "verified local mock build -- aborting (see docs/BUGS.md BUG-0018)",
            file=sys.stderr,
        )
        build_db.finish_run(run_id, "failed")
        sys.exit(2)

    # Per-package gating (docs/CHANGELOG.md, docs/FRD.md COPR-0017): any
    # package not yet clear on every locally-buildable chroot, plus its
    # transitive dependents (which may have built against a stale copy of it),
    # are held back individually -- everything else still submits. Unlike the
    # REQUIRE_CHROOT_COVERAGE abort above, this runs unconditionally; that's
    # what full-cycle-matrix's per-chroot local build is for. Dependents are
    # derived from ineligible_packages() here (spanning every chroot in the
    # matrix), not copr_blocked_packages()'s single-target mock check -- that
    # one is for `full-cycle.py`, where `target` really is the one chroot that
    # invocation just built.
    ineligible = ineligible_packages(copr_repo, packages)
    blocked = block_transitive_dependents(sorted(ineligible), packages, all_packages)

    # #COPR-0007: chain a package behind its own same-run dependencies as
    # Copr build batches, so a dependency rebuilt this same run (e.g. a
    # soname bump forcing a rebuild) lands before its consumers resubmit
    # against it, instead of racing them on packages.yaml's alphabetical
    # order (see docs/features/COPR-0007-copr-submission.md). `packages` is
    # already topologically sorted (prepare_stage()/lib.deps), so by the time
    # a package is reached here every same-run dependency it has has already
    # been submitted (or deliberately skipped -- see below).
    batch_deps = os.environ.get("COPR_BATCH_DEPS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    submitted_build_ids: dict[str, int] = {}
    submitted_depths: dict[str, int] = {}

    failed = False
    submitted = 0
    for pkg, meta in packages.items():
        # Overrides no longer touch version/release (see docs/packaging.md
        # "Per-Fedora-version spec differences") -- only run_for_package needs
        # to resolve apply_os_overrides()'s `_skip`, so it's not repeated here.
        ver = (
            nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
            if meta.get("version")
            else ""
        )

        if pkg in ineligible:
            reason = f"blocked: {ineligible[pkg]}"
            status("copr", pkg, "skip", target, reason, version=ver)
            build_db.set_stage(pkg, "copr", target, run_id, "skipped", reason=reason)
            continue

        if pkg in blocked:
            reason = f"blocked: dependency ineligible: {', '.join(blocked[pkg])}"
            status("copr", pkg, "skip", target, reason, version=ver)
            build_db.set_stage(pkg, "copr", target, run_id, "skipped", reason=reason)
            continue

        after_build_id = None
        depth = 0
        if batch_deps:
            after_build_id, depth = resolve_batch_chain(
                pkg, all_packages, submitted_build_ids, submitted_depths
            )

        submitted += 1
        if not run_for_package(
            pkg,
            meta,
            fedora_version,
            copr_repo,
            proceed,
            target,
            run_id,
            synchronous,
            after_build_id,
        ):
            failed = True

        # Only a row this call actually (re)submitted carries a fresh
        # build_id -- a "_skip"/missing-srpm/missing-mock skip writes no
        # build_id at all, so it naturally never becomes a chain target
        # (there is no new build for a dependent to wait on).
        copr_row = build_db.get_stage(pkg, "copr", target)
        row_build_id = copr_row.get("build_id") if copr_row else None
        if row_build_id:
            submitted_build_ids[pkg] = row_build_id
            submitted_depths[pkg] = depth

    # A per-package hold-back (ineligible/blocked above) is normal and stays
    # quiet -- that's the gate working as designed, including a run where
    # every package happens to be held back for its own genuine reason (a
    # real mock failure and its dependents, say). What must be loud is
    # specifically a *blackout chroot* -- one with zero verified/skipped
    # packages at all (docs/BUGS.md BUG-0051: a brand-new
    # SUPPORTED_FEDORA_VERSIONS entry, or a chroot whose matrix pass never
    # completed) -- because that silently vetoes the entire run and gives no
    # signal why. Gate on blackout_chroots(), not merely `submitted == 0`.
    blackout = blackout_chroots(copr_repo, packages) if packages else []
    if blackout and submitted == 0 and not env_flag("ALLOW_EMPTY_COPR_SUBMISSION"):
        print(
            "\nerror: every package was held back this run -- nothing was "
            "submitted to Copr.",
            file=sys.stderr,
        )
        print(
            "  zero local coverage on: "
            + ", ".join(blackout)
            + " -- run `make matrix-chroot-<version>` to backfill before "
            "the next nightly.",
            file=sys.stderr,
        )
        print(
            "  set ALLOW_EMPTY_COPR_SUBMISSION=true to allow a deliberate "
            "nothing-to-submit run.",
            file=sys.stderr,
        )
        build_db.finish_run(run_id, "failed")
        sys.exit(1)

    build_db.finish_run(run_id, "failed" if failed else "ok")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
