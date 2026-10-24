# COPR-0007. Submit builds to Copr

**Tags:** #copr #publish

## User Story

As a maintainer, I want to submit a verified build to Copr and have the project
description/install docs stay current automatically, so that Copr always reflects
what's actually been built and tested.

## Behavior

`make stage-copr PACKAGE=<name> COPR_REPO=<project>` submits the canonical target's
SRPM to Copr (async `--nowait` by default; `SYNCHRONOUS_COPR_BUILD=true` waits).
Submission is gated **per package**, not all-or-nothing: a package not yet verified
(or deliberately skipped) on every locally-buildable chroot, and its transitive
dependents, are held back individually with a reason naming the chroot — everything
else in the run still submits. If a locally-buildable chroot has zero verified/skipped
packages at all (a "blackout" chroot — e.g. a brand-new Fedora version with no
coverage yet), the whole submission fails loudly instead of silently exiting 0 with
nothing submitted. `REQUIRE_CHROOT_COVERAGE=true` additionally blocks the whole
submission on any gap; `ALLOW_EMPTY_COPR_SUBMISSION=true` opts out of the blackout
failure for a deliberate no-op run.

Submission visits packages in dependency order (`lib.deps`'s topological sort,
via `prepare_stage()`), not `packages.yaml`'s alphabetical order — a package that
itself depends on another package resubmitted this same run is chained behind it
as a Copr build batch (`copr-cli build --after-build-id <id>`), so Copr holds the
dependent's buildroot setup until the dependency finishes, instead of racing it
(#COPR-0007, the `hyprtoolkit` incident below). The chain target is resolved by
`lib.copr.resolve_batch_chain()` from this run's own submission history (a
dependency not being rebuilt this run — already published, or held back by the
ineligible/blocked gate above — contributes no chain edge, since there is nothing
new to wait on). `COPR_BATCH_DEPS=false` disables this and submits every package
independently, matching the old behavior.

After the matrix submits, `make copr-wait` bounds a retry poll
(`lib.copr.poll_copr_status(..., deadline_s=, interval_s=)`) for up to
`COPR_POLL_TIMEOUT` seconds (default 1800), re-checking every `COPR_POLL_INTERVAL`
seconds (default 30), so the docs generated right after (`make readme`) render each
resubmitted package's real state instead of the stale `unknown` it starts async
submission with (#BUG-0039). A package still non-terminal at the deadline keeps
`unknown` in this run's docs. `copr-wait` always exits 0 — a build still running at
the deadline is not a nightly failure. A plain `make full-cycle` resolves such a row
on its next pre-submit `poll_copr_status()` call; the matrix path's `SKIP_COPR`
passes do not poll, which is why submission itself must not depend on that (below).

**Never queue a build twice.** Before submitting, `stage-copr` and `full-cycle` ask
Copr which builds of the project are still in flight (`pending`, `importing`,
`waiting`, `starting`, `running`; `lib.copr.in_flight_builds()`). If the SRPM about
to be uploaded — `<name>-<version>-<release>.fc43.src.rpm`, i.e. the current version
of the application — is already one of them, no `copr-cli build` runs. The row is
recorded `unknown` with that build's existing `build_id` and the reason
`in-progress: build N already on Copr`, so `copr-wait` keeps tracking it and a
dependent package still chains `--after-build-id` behind it. A new version or
release is a different filename and is submitted normally. Under `full-cycle`, a
forced copr stage skips this check (a deliberate resubmission).

**Never rebuild what Copr already has.** After the in-flight check, `stage-copr` and
`full-cycle` also ask Copr for each package's latest *succeeded* build
(`lib.copr.published_builds()`). If that build's SRPM filename equals the one about
to be uploaded, no `copr-cli build` runs: the row is recorded `success` with that
build's `build_id` and the reason `published: build N already on Copr`. This is
exactly "nothing changed" — `update_package_releases()` bumps `release` whenever a
package's own content changes *or a dependency was rebuilt*, so any own or
dependency change yields a new SRPM filename and is submitted normally. A
`published:` row is not a chain target (there is no new build for a dependent to
wait on). `COPR_RESUBMIT=true` (for `stage-copr`) or a forced copr stage in
`full-cycle` (`FORCE_REBUILD`, `force_run`) resubmits anyway. Like the in-flight
check, it fails open: a Copr API failure warns and submits as before.

In `SYNCHRONOUS_COPR_BUILD=true` mode, `run_for_package()` watches `copr-cli build`
to a terminal state itself, bounded by `run_cmd()`'s `CMD_TIMEOUT` (default 3600s).
A watch that is still running when that timeout hits is **not** recorded as a build
failure (#BUG-0107): the submission already succeeded — that's how a `build_id` was
captured from `copr-cli`'s "Created builds: N" line, printed before it starts
watching — and the build itself is still running on Copr. The row is recorded
`unknown` (the same state an async submission starts in) with its `build_id` and a
`reason` explaining the timeout, and `run_for_package()` reports success (the
submission succeeded; only the watch didn't). That row then resolves exactly like an
async one: via `copr-wait`'s bounded poll, or the next run's pre-submit
`poll_copr_status()`. A row's `reason` is now always populated on any non-`success`
outcome, not just the skip-gate reasons above (#BUG-0107).

## Implementation

- `scripts/stage-copr.py`, `scripts/copr-wait.py`, `scripts/lib/copr.py`
  (`ineligible_packages()`/`block_transitive_dependents()`/`blackout_chroots()`/
  `poll_copr_status()`/`resolve_batch_chain()`), `scripts/lib/deps.py`
  (`topological_sort()`, via `yaml_utils.prepare_stage()`).
  `in_flight_builds()` and `published_builds()` feed the guards in
  `stage-copr.py`'s `run_for_package()` (called from `main()` and from
  `full-cycle.py`).
- Requires `copr-cli` configured with `~/.config/copr`.

## Quirks & Decisions

- Decision (#BUG-0039): async submission is kept as-is (making it synchronous would
  serialize dozens of independent Copr builds behind each other); instead
  `_full-cycle-matrix` runs `copr-wait` right after `stage-copr`, bounding the
  retry with a deadline rather than blocking submission itself.
- Quirk: `stage-copr`'s Makefile recipe did not forward `SYNCHRONOUS_COPR_BUILD`
  into the container (unlike `_full-cycle`), so `.env`'s
  `SYNCHRONOUS_COPR_BUILD=true` never reached it in the nightly path — submission
  was silently always async regardless of that setting. Fixed alongside #BUG-0039.
- Quirk (#BUG-0107, discovered the first night #BUG-0039's forwarding fix actually
  took effect): with the forwarding gap closed, `.env`'s stale
  `SYNCHRONOUS_COPR_BUILD=true` became live for the first time and serialized 51
  Copr builds into a single ~15h nightly (run 159, 2026-09-22). Once Copr's queue
  slowed, the remaining watches each hit `CMD_TIMEOUT` an hour apart and were
  recorded `failed` with `build_id`/`reason` both `NULL` — unresolvable by
  `poll_copr_status()`, which only resumes a row that has a `build_id` *and* a
  non-terminal state — even though all 5 packages had already succeeded on Copr.
  Fixed two ways: `.env`'s nightly default is async again (reaffirming the decision
  above), and a watch timeout is now recorded `unknown`+`build_id`+`reason` rather
  than a stranded `failed` (see Behavior above) — so a stray manual
  `SYNCHRONOUS_COPR_BUILD=true` run can no longer strand a row either.
- Quirk: copr rows are keyed by one local `target`, but Copr fans a submission out to
  its own chroot set — a real per-chroot matrix view needs `stage_results` (or a
  separate table) keyed by the Copr chroot, not the local one.
  Proposed: see [COPR-0021](COPR-0021-copr-chroot-matrix.md) (Planned).
- Quirk: aarch64 chroots always report "not verifiable locally" (no cross-arch build
  path exists) and can never satisfy the per-chroot coverage gate.
  Open: see [COPR-0020](COPR-0020-aarch64-local-builds.md) (Planned).
- Quirk (motivating case for build-batch chaining): run 163 (2026-09-28) submitted
  51 packages in `packages.yaml`'s alphabetical order. Rawhide bumped
  `abseil-cpp`'s soname that day, making the `hyprtoolkit` already published on
  Copr uninstallable (`nothing provides libabsl_hash.so.2605.0.0()(64bit)`
  needed by the old `hyprtoolkit` build). Run 163 *did* submit a rebuilt
  `hyprtoolkit` (build 11044603) that would have fixed this — but alphabetically
  after its four consumers (`hyprland-guiutils`, `hyprlauncher`, `hyprpaper`,
  `hyprpolkitagent`, builds 11044585/92/94/96), which resolved their
  `hyprtoolkit-devel` buildreq against the still-broken old copy and failed
  `dnf5 builddep` on both rawhide chroots. `depends_on` was declared correctly
  for all four; it was only ever consulted for blocking
  (`block_transitive_dependents()`), never for ordering. Fixed by this feature's
  topo-sort + `--after-build-id` chaining.
- Decision: chaining targets the dependency with the greatest existing batch
  depth, not every submitted dependency — Copr's build-batches model serializes
  globally (batch N fully completes before N+1 starts, regardless of which build
  in N a later one names via `--after-build-id`), so waiting on the deepest
  predecessor already implies every shallower one has finished. See
  `resolve_batch_chain()`'s docstring and
  https://pavel.raiskup.cz/blog/build-ordering-by-batches-in-copr.html.
- Verified (#COPR-0007 implementation): Copr's build-batches feature and its
  `copr-cli build --after-build-id BUILD_ID` flag are documented upstream
  (https://pavel.raiskup.cz/blog/build-ordering-by-batches-in-copr.html); no
  fallback wave/poll scheme was needed. (Not independently re-verified against
  this repo's own `rpm-toolbox` image, which wasn't built on the implementing
  host at the time — confirm with `copr-cli build --help` after
  `make container-build` if upstream ever drops the flag.)

- Decision: the in-flight check asks Copr, not the local DB. `prepare_stage()` clears
  the copr rows (pending `build_id`s included) at the start of every `stage-copr`
  run, and the matrix path's `SKIP_COPR` passes never poll, so the local DB cannot
  say what is queued. Run 311 (after runs 298 and 303) left 163 pending builds on
  Copr that were only 55 distinct SRPMs, 54 of them duplicated up to 4x. A pending
  build has no package name or version server-side until it is imported, but its
  `source_package.url` ends in the uploaded SRPM filename, so that filename is the
  key (the highest build id wins if there are several).
- Decision: `in_flight_builds()` reads the project's builds newest-first and filters
  by state itself, instead of using the API's `status=` filter. Measured against
  `nett00n/hyprland`, each `status=` call takes ~12 s whatever the page size (even
  with no results), so five of them could not fit any reasonable timeout, while the
  plain listing answers in ~2 s. It stops at the first page with nothing in flight
  (200 builds per page, at most 5 pages, 30 s timeout), so a build stuck far behind
  a long run of finished ones is not seen.
- Quirk: Copr stores an uploaded SRPM under a sanitized filename (characters outside
  `[A-Za-z0-9._-]` are dropped), so a snapshot version such as
  `hyprland-plugins-0.56.0^20260805git00862ca-8` is `...0.56.020260805git...` on Copr.
  Both sides are compared through `lib.copr.srpm_key()`; without it every
  caret-versioned package would be resubmitted on every run.
- Decision: the check fails open. If the Copr API cannot be reached or parsed,
  `in_flight_builds()` warns and returns nothing, and submission proceeds as before
  (the same stance as `get_project_chroots()`).
- Quirk: run 368 (2026-10-24) submitted 57 SRPMs of which about 50 had the same
  name-version-release as builds that had already succeeded (e.g. `hyprutils-0.14.3-1`,
  `waylock-1.6.0-4`, both uploaded by run 361 hours earlier) — the in-flight guard
  only sees unfinished builds, so every finished one was re-queued on the next run.
  Fixed by the "never rebuild what Copr already has" guard above.
- Decision: `published_builds()` uses one project-wide
  `package/list?with_latest_succeeded_build=True` call (200 packages per page, ~2.5 s
  for the whole project) instead of a per-package query, keyed by the same
  `srpm_key()`-normalized SRPM filename as `in_flight_builds()`. Unchanged-ness is
  decided by the filename alone because the release auto-increment already cascades
  dependency rebuilds into it.

## Testing

### Unit

- `tests/test_copr.py` (incl. `poll_copr_status`'s bounded-retry `deadline_s`/
  `interval_s` behavior, `in_flight_builds()` and `published_builds()`),
  `tests/test_pipeline_copr_stage_utils.py`.
- `tests/test_subprocess_utils.py` (`run_cmd()` preserving a killed command's
  partial stdout/stderr and log on `TimeoutExpired`, #BUG-0106).
- `tests/test_pkg_log_analysis.py::TestCoprIssuesInSummary` (#BUG-0108: a
  non-`success`/`skipped` copr row surfaces in `docs/nightly-summary.md`, and only
  a genuinely `failed` one — not `unknown` — fails the run).

### Integration

- `tests/integration/test_entry_points.py` (incl.
  `test_copr_sync_watch_timeout_is_unknown_not_failed` and the already-in-flight
  skip), `tests/integration/test_make_targets.py`.

## Status

Implemented
