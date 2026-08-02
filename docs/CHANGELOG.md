# Changelog

Tracks changes to this repo's automation - Makefile targets, script behavior,
`packages.yaml` schema, build pipeline stages, breaking contributor-facing
changes. Routine package adds/version bumps/release increments are NOT logged
here (see `packages.yaml` git history, `docs/full-report.md`, or `blog/`
instead).

Newest first. One `## YYYY-MM-DD` section per day with changes; one bullet per
entry as `- <Added|Changed|Fixed|Removed>: <what changed>`. Full ruleset in
`docs/CONTRIBUTING.md` "Changelog".

History before this file's introduction is not backfilled - see `git log`.

## 2026-08-02

- Changed: `make update-daily` no longer runs the full `pre-commit` gate (test+lint+fmt) before
  building -- just the new `validate-packages` target (packages.yaml/.gitmodules structure
  checks, extracted from `pre-commit`'s first line so both can reuse it) plus `fmt`. `scripts/`
  lint/test health is already CI's job on every push/PR; an unrelated regression there no longer
  blocks a nightly Copr publish (closes TODO-0064). Also: a package build failure inside
  `full-cycle` no longer aborts the rest of the run -- `readme`/`copr-description`/`git commit`
  still happen (so the night's version bumps aren't lost), and `update-daily` reports the
  failure and exits non-zero only at the end, after everything else has run (closes TODO-0061)
- Changed: `PACKAGE` env var semantics on the Makefile, closing TODO-0029 -- `gather-requires`
  (the one target where it was a filesystem path to a built `.rpm`, not a packages.yaml key)
  now takes `RPM=` instead; `list-tags`/`scaffold-package`/`add-submodule`/`delete-package`
  (single-package-only targets) now reject a comma-separated `PACKAGE` with a clear error
  instead of a confusing downstream one (`KeyError`, wrong path, silent no-op); `sources`/
  `stage-log-analyze` now accept the same comma-separated-list shape every other multi-package
  target already does, instead of silently treating `PACKAGE=a,b` as one bogus package name
- Added: `make full-cycle-matrix` builds every `MATRIX_VERSIONS` (default: all `SUPPORTED`)
  Fedora version's x86_64 chroot locally via mock, then submits to Copr once; and
  `stage-copr`/`full-cycle` now print a per-chroot local-mock coverage table (verified/failed/
  unbuilt/not-locally-verifiable) before every Copr submission, warning by default and blocking
  under `REQUIRE_CHROOT_COVERAGE=true`. Narrows BUG-0018 to its aarch64 residual (blocked on
  TODO-0024) -- x86_64 chroot-specific failures are now catchable before submission
- Fixed: `update-versions.py:pull_submodule()` no longer force-moves every submodule to upstream
  HEAD regardless of `auto_update.release_type` -- a `pinned-tag`/`pinned-commit`/`pinned-version`
  package now gets its submodule checked out *detached* at `refs/tags/<tag>` /
  `source.commit.full` / `refs/tags/v<version>` (falling back to the bare `<version>` tag for
  upstreams that don't use a `v` prefix), and an unresolvable pin leaves the checkout exactly
  where it is instead of falling back to branch HEAD, so `update-daily`'s `git add submodules/`
  stops committing a moved gitlink under a package the operator believes is frozen (closes
  BUG-0033 -- the `update-versions.py:pull_submodule()` one, not the unrelated `.git`-suffix entry
  reusing that ID lower in this file). A pin also now wins over a moving sibling sharing the same
  submodule url, safe because version resolution no longer reads the working tree:
  `lib/gitmodules.py:get_submodule_commit_with_base()` takes a `ref`, so `latest-commit`/default
  packages resolve `origin/<branch>` instead of whatever HEAD happens to be, and
  `lib/cache.py:_source_commit()` reads `source.commit.full` from packages.yaml -- the hash the
  build actually downloads via `%{commit}` -- instead of the live checkout. `git fetch` now passes
  `--tags` so a pinned tag resolves even when unreachable from the tracked branch
- Fixed: `lib/cache.py:_source_commit()` now returns `None` for every package except the 3 whose
  `auto_update.release_type` is `latest-commit`/`pinned-commit` (the ones that actually build from
  `%{url}/archive/%{commit}.tar.gz`) instead of hashing the submodule's live checkout for all 45 --
  a nightly submodule pull no longer flips every release package's cache and forces an
  unchanged-version rebuild+resubmit (closes BUG-0034, BUG-0001)
- Fixed: `lib/yaml_utils.py:update_package_releases()` now decides "needs a release bump" from the
  same full input-hash set (`source_commit`/`templates`/`package_config`/`dependencies`/`patches`)
  that `lib/pipeline.py:is_cached()` uses to decide "needs an actual rebuild", instead of the
  package's own content hash alone -- a rebuild triggered by an edited template/patch or a
  dependency's config change now always gets a release bump, so a different RPM never ships under
  an NVR already on Copr (closes BUG-0035)
- Fixed: `make update-daily` no longer fails on a no-op night (nothing staged skips the commit
  instead of `git commit`'s nonzero exit aborting the target), and `PUSH=1` now rebases onto
  `origin/main` before pushing so it doesn't collide with `publish-readme.yml`'s own `[skip ci]`
  push to `main` (closes BUG-0037, BUG-0038)
- Added: this changelog and its ruleset (see docs/CONTRIBUTING.md)
- Added: CI (GitHub Actions) runs lint+test on every push/PR, natively via `NO_CONTAINER=1`
- Changed: `make update-daily` now runs the `pre-commit` quality gate (validate+test+lint+fmt)
  before building, instead of `fmt` alone; merged five separate `$(MAKE)` sub-processes into one
  (closes TODO-0034); narrowed its `git add` to generated paths only (no longer stages
  `templates/`/`blog/`); added `PUSH=1` to push after committing
- Changed: moved `CONTRIBUTING.md` and `CHANGELOG.md` to `docs/`; split `CONTRIBUTING.md` into
  `docs/CONTRIBUTING.md` (contributor onboarding), `docs/operations.md` (maintainer runbook),
  and `docs/packaging.md` (`packages.yaml` schema reference); folded `docs/features/*.md` into
  `docs/FRD.md`
- Removed: dead `docs/build-report.html` (nothing generated or referenced it)
- Fixed: Makefile help text and moved/rewritten CONTRIBUTING both called Rust vendoring
  "ABANDONED"/"Go packages only", though `vendor_rust.py` is live for 2 packages (closes
  TODO-0051)
- Changed: `docs/bugs.md`/`docs/todo.md` got a scope rule, a `## Next` section, and an
  ID-reuse rule; deleted 4 entries that verbatim-duplicated the other file (TODO-0061/0062 vs.
  BUG-0028/0029) and TODO-0034/TODO-0051 (both fixed above)
- Fixed: `requirements.txt`/`requirements-dev.txt` now pin `~=X.Y.Z` (PEP 440 compatible-release:
  patch upgrades allowed, minor/major blocked) instead of open-ended `>=` floors. Found while
  wiring CI: the repo has no ruff config, so its lint behavior rides ruff's default rule set
  with nothing pinning it - `ruff==0.15.4` passes scripts/ clean, `ruff==0.16.1` (satisfies the
  old `>=0.15.4`) flags 124 errors on the exact same code (new default-enabled rules incl.
  SIM118/BLE001/N999/EXE001). A plain `make setup-venv` + `make lint` on a fresh clone was one
  `pip install` away from failing on unrelated code, independent of any PR's actual changes
- Removed: Fedora 42 (EOL) from `SUPPORTED` in the Makefile, the `.env.example` comment, and a
  stray test name - the maintainer had already announced dropping it back in `blog/NEWS.md`'s
  2026-03-10 entry, but the Makefile's version list was never actually updated to match
- Changed: merged 8 separate `blog/*.md` posts into one microblog-style `blog/NEWS.md`
  README's News section now shows the most recent entries (default 8,
  configurable via `repo.yaml` `documents.news_limit`) instead of just the latest one -
  `get_recent_news()` (`lib/readme_content.py`, replaces `get_latest_blog()`) extracts
  `## `-delimited sections instead of glob-sorting filenames - closes TODO-0063 (mixed
  per-day/per-month filenames had a latent lexicographic-sort collision) since there's only one
  file now
- Added: `repo.yaml` `documents.sections` - per-block visibility toggle (`news`/`docs`/
  `support`/`license`/`authors`/`maintainers`/`contributors`/`additional_info`) for generated
  docs, defaulting to `true` when unset. `__header.j2`/`__footer.j2` gate each block on it;
  useful as an immediate workaround for BUG-0030 (`contributors: false`) without touching the
  underlying template
- Added: `scripts/gen-readme-shell.py` / `make readme-shell` - regenerates only the branding
  shell (header/footer) of `README.md`/`docs/README.copr.md` by splicing rendered
  `__header.j2`/`__footer.j2` between their existing marker comments, leaving the
  packages/build-status body untouched. Needs no `build-report.db` (gitignored, so CI has none)
  unlike `make readme`/`gen-report.py`, which derives its entire package list from DB rows and
  would render zero packages on a from-scratch checkout. Moved the now-shared
  `collect_contributors`/`get_recent_news`/`get_sections` out of `gen-report.py` into new
  `lib/readme_content.py` so both scripts use the same code
- Added: `.github/workflows/publish-readme.yml` runs `make readme-shell` on every push to
  `main` and on manual dispatch, auto-committing (`[skip ci]`) and pushing if anything changed
- Fixed: stage cache now verifies the recorded artifact is still on disk before skipping a
  stage (`lib/pipeline.py:artifacts_present()`, version-scoped against `artifacts` rows), and
  `stage-mock.py`/`stage-copr.py` refuse a recorded-but-missing SRPM instead of handing it to
  mock/copr-cli (closes BUG-0015, TODO-0016)
- Fixed: `Waybar-git`/`hyprland-plugins-git` `packages.yaml` `url` didn't exactly match their
  `.gitmodules` submodule url (a stray/missing trailing `.git`), so `update-versions.py`'s
  exact-match lookup silently skipped their `auto_update` every run; also found and fixed 5 more
  packages hitting the same class of drift (`cpptrace`, `libdwarf-code`, `eww`,
  `snappy-switcher`, `mpvpaper`) plus a `Waybar` (stable) regression this fix would otherwise
  have introduced via the shared submodule url (closes BUG-0013). Added
  `validate_submodule_url_resolution()` (`lib/validation.py`, wired into `stage-validate.py`)
  and an equivalent check in `validate-packages.py` (the pre-commit gate) so this can't recur
  silently again
- Removed: dead `scripts/validate-package-urls.py` (closes TODO-0037) -- unreferenced outside
  its own test, and its url-matching logic normalized away the exact `.git`-suffix difference
  that causes BUG-0013's failure mode, so it would not have caught it even if wired in
- Fixed: `aylurs-gtk-shell`/`cava`/`glaze`/`gtk4-layer-shell`/`Hyprshot`/`pyprland`/`cliphist`
  `url` had a stray trailing `.git` while their `source.archives` template uses `%{url}/archive/...`
  directly -> the generated Source0 404s on GitHub (confirmed live via `curl -I` before and after
  for all 7); masked until now only because each package's srpm stage was cached from before the
  `.git` was added. Dropped `.git` from both `packages.yaml` and the matching `.gitmodules`
  submodule url for all 7, keeping url-resolution and archive-fetch correctness in sync (closes
  BUG-0033). `quickshell`'s url was investigated too but left unchanged: its git host
  (`git.outfoxxed.me`, Gitea) serves an identical archive either way, confirmed by byte-identical
  `content-length` with and without `.git`
