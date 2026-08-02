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
