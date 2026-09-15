# Roadmap — ordering of `docs/BUGS.md` + `docs/TODO.md`

## Context

`docs/BUGS.md` (57 open, next ID BUG-0104) and `docs/TODO.md` (3 open, next ID
TODO-0094) are both well-groomed — every entry has a verified root cause, a
`[P#/D#]` marker, and file:line evidence. `docs/features/` (5 Planned docs) carries
the substantial not-yet-built work. What none of them have on their own is an
**order**. Entries are filed by topic (Scripts / Makefile / Build report db / …), and
several carry explicit sequencing notes scattered through their bodies ("should land
before BUG-0093", "best folded into BUG-0061's schema migration", "do together with
BUG-0083"). Picking the next task today means re-reading hundreds of lines and
re-deriving those constraints by hand.

This roadmap does that once: it groups the open `BUGS.md`/`TODO.md` items and Planned
feature docs into 7 epics, orders the epics, orders the items inside each epic, and
records the hard blockers. **Nothing here changes priorities or invents work** — every
item keeps its existing ID and `[P#/D#]`; this is purely sequence.

North star chosen for this ordering: **nightly reliability** — make
`make update-daily` trustworthy first, expand the matrix second, pay down
structural debt third. `docs/package-requests.md` is explicitly out of scope (it's
a package wishlist, not tasks). `docs/FRD.md`'s 18 Implemented features describe
today's capabilities, not future ones, so they constrain nothing here — its 5 Planned
features are what Epics 4–5 and 7 sequence.

This roadmap will drift as items close (entries are deleted from `docs/BUGS.md`/
`docs/TODO.md` on fix, and a Planned feature doc's checkbox flips once shipped, per
those files' own convention) — re-check and prune it periodically; see "Keeping this
current" at the end.

---

## Epic sequence at a glance

| # | Epic | Why here |
| --- | --- | --- |
| 1 | Clear the desk | All D1. Removes footguns that make every later epic slower to verify. |
| 2 | Guardrails | Every one of these automates a check a human already did by hand. Must precede refactors. |
| 3 | Build-db memory | One schema migration, done once, with Epic 5's needs designed in. |
| 4 | Observability | Depends on Epic 3's `run_id`; makes nightly failures diagnosable. |
| 5 | Matrix / multi-target | The keystone refactor (3 Planned features). Deliberately after the schema settles. |
| 6 | Structural debt | Safe only once Epics 2–3 exist to catch regressions. |
| 7 | Cosmetic + deferred | No dependents. Fill-in work, or explicit decisions to park. |

---

## Epic 1 — Clear the desk

*All D1/trivial. Two of them (BUG-0055, BUG-0080) actively break the test loop
you'll lean on for every later epic, and two (BUG-0052, BUG-0009) are live
footguns during manual pipeline runs. Do the whole epic in one sitting.*

Order:

1. **BUG-0055** — `test_addrepo_still_added_when_local_repo_has_repodata` fails on
   a bare host (`createrepo_c` not patched). Blocks running `pytest` outside the
   container. *First because it's the fastest path to a green suite on the host.*
2. **BUG-0080** — `tests/conftest.py`'s `fake_repo` writes invalid YAML. Every
   test that needs a parseable `packages.yaml` currently works around it.
3. **BUG-0079** — `get_packages()` binds `PACKAGES_YAML` at import time, so
   `fake_repo` can't redirect it. Together with -0080 this makes the fixture
   actually usable; both were found *while writing tests* for BUG-0078, which is
   Epic 2.
4. **BUG-0052** — de-duplicate `.env` (`SKIP_COPR` assigned twice, last wins →
   a plain `make full-cycle` submits to Copr when line 18 says it won't). Refresh
   the stale `FEDORA_VERSION` comment. *Do before any manual pipeline runs.*
5. **BUG-0009** — remove the dead `DRY_RUN` passthrough (nothing in `scripts/`
   reads it; `FORCE_REBUILD` replaced it).
6. **BUG-0006** — `make container-enter` ≠ `$(CONTAINER_RUN)`. Needed for
   hands-on mock debugging in Epics 3–5.
7. **BUG-0099** — gate the unconditional 5s post-plan sleep on `isatty()`; paid
   3× per matrix run in the unattended cron flow.
8. **BUG-0082** — `set-package-release.py`'s `--lock` detected by argv membership.
9. **BUG-0081** — `format-yaml.py`'s `indent_spaces` is a dead config path.
10. **BUG-0086** — delete `reporting.badge()`, `badge_short()`, the
    `load_packages` alias.
11. **BUG-0102** — rename `write_yaml_preserving_comments()` (it doesn't).
12. **TODO-0011** — run `make fmt` after scaffolding.

**Done when:** `pytest tests/` green on a bare host; `.env` says what it means.

---

## Epic 2 — Guardrails

*Each item here turns a defect-class that was caught by hand into a check.
BUG-0097 is sequenced before Epic 6's typing work by its own note. BUG-0078
lands here rather than in Epic 6 because the three untested scripts are the ones
later refactors would silently break.*

Order:

1. **BUG-0073** — duplicate `#BUG-`/`#TODO-` ID check in `make pre-commit`. D1,
   and it protects the two files this entire roadmap indexes. *Do first.*
2. **BUG-0097** — field→type table in `lib/validation.py` (a float `version: 1.9`
   passed both validators). Explicitly a prerequisite for BUG-0093.
3. **BUG-0089** — cross-validate the vendoring trigger (`build_requires`
   containing `golang`/`cargo`) against packages.yaml's `Source1` + `tar xf`.
   Two sources of truth, no check.
4. **BUG-0056** — automated check for `latest-commit` outrunning a tag-pinned
   `depends_on`. This is the drift that broke `hyprland-plugins` across all three
   chroots (runs 76–78) and was only caught by mock failing. *Needs -0097's
   validation scaffolding to hang off.*
5. **BUG-0078** — tests for `gather-requires.py`, `gen-readme-shell.py`,
   `list-tags.py`. Unblocked by Epic 1's fixture fixes.
6. **BUG-0096** — widen ruff beyond default `E,F`. Select `B,RUF,SIM` + the
   useful `PLW` subset; leave `PLR0912/0913/0915` and `N999` off (they fire on
   files already tracked as BUG-0076/-0083). Catches 8 real `PLW2901`
   loop-variable bugs.
7. **BUG-0072** — `KeyboardInterrupt` handler in the 16 scripts lacking one. At
   minimum `update-versions.py`, the longest-lived script in the nightly run.

**Done when:** `make pre-commit` fails on a duplicate tracker ID, a mistyped
packages.yaml scalar, and a vendoring/Source1 mismatch.

---

## Epic 3 — Build-db memory

*The "why did run N rebuild 19 packages" pain, plus the cache lying about
dependencies. Item 4 is a single schema migration — design it once with the arch
column (BUG-0065) and the copr-chroot dimension
([COPR-0021](features/COPR-0021-copr-chroot-matrix.md)) in mind even though the
latter lands in Epic 5, so the table isn't bumped twice.*

Order:

1. **BUG-0063** — append-only `stage_history` table keyed by
   `(package, stage, target, run_id)`. D2, and `run_id` already threads through
   every `set_stage()`/`finalize_stage()` call site, so it's an extra insert with
   no caller plumbing. *First: it's the cheapest, and it starts accumulating the
   history the rest of this epic wants to read.*
2. **BUG-0059** — `last_success` alongside `last_attempt`. Same root cause as
   -0063; do immediately after, on the same table design.
3. **BUG-0064** — verify a cached package's *dependencies'* RPMs still exist in
   `local-repo/<target>/`. Today `is_cached()` checks only the package's own
   artifact, and the one check that would notice (`check_buildroot_repo()`) runs
   inside the path the cache skips.
4. **BUG-0061 + BUG-0065** — artifact `sha256` (with an mtime/size guard) and
   the `arch` column, as **one** migration. -0065's own entry says to fold it in.
5. **BUG-0057** — stop `spec.j2` edits force-rebuilding all 49 packages; report
   "spec generated from an outdated template" instead.
6. **BUG-0058** — track the generator version as a cache input; report packages
   last built with an older generator. Same code path as -0057.
7. **BUG-0098** — collapse the byte-identical `_content_hash()` /
   `_package_config_hash()`. *Deliberately last in this epic:* it invalidates
   every cached row and forces a full 49-package rebuild, so it should ride along
   with whichever of -0061/-0057 already costs a rebuild rather than paying twice.
8. **BUG-0060** — `make db-export` (sqlite → yaml/json snapshot). D1, and useful
   input to BUG-0031 in Epic 4.
9. **BUG-0062** — host-side path resolution for `db-shell`/`db-usage`/`db-prune`.
   Can only ever be partial (the rpmbuild volume has no host path at all) — take
   the repo + vendor-store realms and say so.

**Done when:** you can answer "why did package X rebuild in run N" after run N+1 has
run, and a missing dependency RPM invalidates the cache that depends on it.

---

## Epic 4 — Observability

*Depends on Epic 3's `run_id` being a real, queryable dimension. This is what
turns "update-daily reported success and pushed nothing" (the 2026-09-07/08
incident) into something visible the same night.*

Order:

1. **[COPR-0022](features/COPR-0022-run-scoped-logs-and-summary.md)** (Planned
   feature) — one path restructure, not two: add the distro/version segment *and*
   the run-id nesting (`logs/<run_id>/<distro>-<version>/<package>/`) in a single
   change, with the retention/prune policy in the same commit, then a durable
   nightly summary (`pkg-log-analysis.py --output <file>`) linking to those
   per-run logs. Split the live-tailing half (bind-mount mock's resultdir) out as
   a separate, cheap follow-up — it's independent of the layout.
2. **BUG-0100** — aggregate the 10 warn-and-continue sites in
   `update-versions.py` into one failure report. Today a single `git fetch`
   failure is invisible and a package silently sits on a stale version.
3. **BUG-0039** — resubmitted packages publish as `unknown` (async `--nowait`
   submit, `readme` runs seconds later, one poll too early).
4. **BUG-0031** — CI check that generated docs still match
   `packages.yaml`/`build-report.db`. Needs the design decision its entry names
   (snapshot vs. partial diff) — **BUG-0060's `db-export` from Epic 3 is the
   natural answer**, which is why it's sequenced after.
5. **BUG-0101** — concurrency in `update-versions.py`'s per-submodule loop.
   Split from BUG-0100 as materially riskier (shared `.git/modules`); do it only
   once BUG-0100's aggregate reporting can show what broke.

**Done when:** a failed nightly leaves a committed summary pointing at logs that still
exist tomorrow.

---

## Epic 5 — Matrix / multi-target

*Currently everything outside the db key is fedora+x86_64-hardcoded.
[COPR-0019](features/COPR-0019-build-target.md) is named in its own doc as "the
keystone item for the whole section" — nothing else here is worth starting first.
These three items are Planned features (`docs/features/`), not `BUGS.md`/`TODO.md`
entries — see `docs/ID-MIGRATION.md` for what each absorbed.*

Order:

1. **[COPR-0019](features/COPR-0019-build-target.md)** — `TARGET` (or
   `DISTRO`+`ARCH`) env var. `SUPPORTED`, `mock_chroot()`, the `Containerfile`
   FROM, and `lib/paths.py`'s module-level `DISTRO`/`ARCH` constants are all
   fedora-hardcoded; also folds in the arch-keyed mock-cache/mock-root volumes,
   distro-agnostic `packages.yaml` override keys, `nvr()`'s hardcoded `.fcNN`, and
   the cosmetic SRPM dist-tag mismatch it causes. D4, and everything below
   depends on it.
2. **[COPR-0021](features/COPR-0021-copr-chroot-matrix.md)** — key copr rows by
   COPR chroot instead of the single local target, and render a package × target
   matrix report. Schema change — reuse Epic 3.4's migration shape.
3. **[COPR-0020](features/COPR-0020-aarch64-local-builds.md)** — aarch64 local
   builds (qemu-user-static binfmt or a native runner). The only **P1**-flagged
   item in either tracker before its promotion, sequenced here deliberately:
   doing it before COPR-0019 means doing the `DISTRO`/`ARCH` constant work twice.
   Mostly a multi-day infra decision, not a code change.
4. **BUG-0018 residual** — closes once COPR-0020 lands; aarch64 chroots stop
   reporting "not verifiable locally" and can finally satisfy
   `REQUIRE_CHROOT_COVERAGE`.

Deferred within this epic: **BUG-0067** (parallel matrix chroots) — needs both
the shared-`packages.yaml` write (`SKIP_RELEASE_BUMP`) and the pipeline `flock`
solved first; park until the matrix is correct before making it fast.

**Done when:** a non-fedora or non-x86_64 target runs end to end without editing
constants.

---

## Epic 6 — Structural debt

*Everything here is a refactor with no behavior change, which is exactly why it
comes after Epics 2–3: the guardrails and the test coverage are what make these
safe. Ordered so each step shrinks the surface for the next.*

Typing track (do as a unit, in this order — each unlocks a mypy flag):

1. **BUG-0094** — `Stage`/`State` `Literal` aliases (~190 hand-retyped literals
   across 16 files). D2, biggest ratio of risk-removed to effort; the same failure
   shape as the already-closed BUG-0002/BUG-0014.
2. **BUG-0093** — `TypedDict`s for the stage row, package metadata, and
   `compute_input_hashes()`. Unlocks `disallow_any_generics` (155 errors). Start
   with the stage row — it's the one with the documented-but-unenforced
   "drops NULL columns" contract. *Prerequisite: BUG-0097 (Epic 2.2).*
3. **BUG-0095** — typed loader wrappers at the `yaml.safe_load`/`json.loads`
   trust boundaries. Unlocks `warn_return_any` (17 errors).

Large-file track:

4. **BUG-0083 + BUG-0087** — `lib/log_analysis.py` (1257 lines, ~41 copy-pasted
   regex blocks) → a `(regex, formatter)` data table, and fix
   `pkg-log-analysis.py`'s eight private imports in the same pass (-0087's entry
   says the refactor moves those boundaries anyway). Unusually safe: two existing
   test files cover it well.
5. **BUG-0076 + BUG-0077** — `run_build_pipeline` (425 lines) → a stage-runner
   abstraction, with the per-stage "config: skip" copy-paste extracted into a new
   `lib/stage_common.py`. -0076's entry says to do them together.
6. **BUG-0074** — `gen-spec.py` (446 lines, duplicates `lib/github.py` almost
   verbatim, no Makefile target, used only by its own test). Check
   `build_context()` for spec-rendering logic `stage-spec.py` lacks, then delete
   or replace with lib calls.

Vendor + Makefile track:

7. **BUG-0084 + BUG-0090** — move `vendor_golang.py`/`vendor_rust.py` onto
   `run_cmd`; -0090 (`_log_fn` private-but-imported) resolves itself as a result.
   Watch `vendor_rust.py:62`'s probe call.
8. **BUG-0091** — stream `_download()` to disk instead of reading whole archives
   into memory. D1; `verify_download()` runs right after either way.
9. **BUG-0092** — the vendor stage's missing `log` field on 5 skip paths. Decide
   first whether an empty-file log beats `NULL` for the report renderer.
10. **BUG-0070 + BUG-0071** — move `add-submodule`/`add-new`/`delete-package`
    logic out of Makefile recipes into `scripts/*.py` (untestable today), and in
    the same pass make `delete-package` unlink `local-repo/*/<pkg>-*.rpm` plus
    regenerate repo metadata. -0071 notes these RPMs are now *worse off* than
    before — they survive with no db row pointing at them.
11. **BUG-0069** — `ALL_PACKAGES` grep→yaml. D1 but needs a cache, not a straight
    swap: it's a parse-time `$(shell)` on *every* make invocation.
12. **BUG-0066** — pick one of the two coexisting multi-package loop strategies.
13. **BUG-0068** — `HIGHLIGHT_PREFIX`'s baked-in quote chars (~80+ echo sites).
14. **BUG-0075** (conftest dedupe) and **BUG-0085** (docstrings stating which
    YAML lib to use when) — fill-in, any time.

**Done when:** `disallow_any_generics` and `warn_return_any` on in `mypy.ini`; no
first-party file over ~500 lines.

---

## Epic 7 — Cosmetic, deferred, and decisions

*No dependents, no urgency. Two of these are decisions to make rather than tasks
to do — resolve them explicitly so they stop sitting in `## Unsorted`.*

1. **BUG-0030** — contributors render concatenated (`trim_blocks` eats the newline
   after `{% endif %}`) *and* `collect_contributors()` dedupes by name not email.
   Needs both fixes. D1; visible today at `docs/full-report.md:1072`.
2. **BUG-0047** — `normalize_file_entry` never canonicalizes the 39 already-
   `%{_prefix}/...` entries; no `/usr/lib` in `PREFIXES`. Cosmetic.
3. **BUG-0088** — Containerfile reproducibility. The honest fix is digest-pinning
   the base image, not pinning individual packages against a floating base.
4. **BUG-0103** — apply DDD's `#COPR-NNNN` comment convention to every top-level
   function implementing a feature. No dependents; a mechanical pass once the
   feature docs it references (this whole `docs/features/` migration) have
   settled.
5. **[COPR-0023](features/COPR-0023-source-signature-verification.md)** (Planned
   feature) — `git tag -v` verification for upstreams that sign tags (its old
   submodule-init blocker is gone); GPG/detached-signature verification stays
   explicitly parked in the same doc — 43/45 sources are GitHub auto-generated tag
   archives, which GitHub doesn't sign. Revisit that half only when a genuinely
   signed upstream release shows up.
6. **TODO-0010** — "separate prod and local debug builds". **Decide or delete** —
   no stated problem or acceptance criterion today.
7. **TODO-0013** — split management system from repo content (`#2.0`). **Decide or
   delete** — a repo-topology ruling, not a task.
8. Unresolved note in `blog/NEWS.md` (2026-08-09): Hyprland f43 builds locally with
   LionHeartP's patch but still fails on Copr. Not filed in either tracker —
   **file it as BUG-0104 or record that it's stale**, since it's the same shape as
   BUG-0018.

---

## Keeping this current

- **Consistency with the trackers.** Confirm every open ID appears exactly once
  here:
  `grep -oE '^- #(BUG|TODO)-[0-9]+' docs/BUGS.md docs/TODO.md | grep -oE '(BUG|TODO)-[0-9]+' | sort`
  against the IDs cited in this file, plus every Planned entry in `docs/FRD.md`
  against its `[COPR-NNNN]` citations here. 60 tracker items (57 BUG + 3 TODO) and 5
  Planned features as of 2026-09-15 (the DDD-adoption migration — see
  `docs/ID-MIGRATION.md`). Any ID in one list and not the other is a roadmap bug.
- **Blocker claims.** Each "blocked on X" above is quoted from the entry's own
  body in `docs/TODO.md`/`docs/BUGS.md` — re-check there if an entry is edited.
- **As items close.** Entries are deleted from `docs/TODO.md`/`docs/BUGS.md` when
  fixed (the fix gets a `docs/CHANGELOG.md` bullet), so this roadmap will drift.
  Re-run the grep above at the end of each epic and prune closed items from here.
- **BUG-0073 (Epic 2.1)** is the automated half of the ID-consistency check —
  once it lands, `make pre-commit` catches duplicate IDs, and the manual grep
  above is only needed for the roadmap-vs-tracker comparison.
