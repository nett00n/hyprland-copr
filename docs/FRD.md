# FRD — Feature Requirements

Automation features of this repo, one-liners + tags.

- **COPR-0001** Add a new package from an upstream URL in one command, registering the git submodule and scaffolding its `packages.yaml` entry. `#packages #onboarding`
- **COPR-0002** Run the full build pipeline (spec → vendor → srpm → mock → copr) for one or all packages with a single command. `#build #pipeline #copr`
  Each stage is individually skippable/forceable and cached by content hash, so unchanged packages are skipped on rerun.
- **COPR-0003** Run the end-to-end daily update: bump versions, run the quality gate, build, regenerate docs, push COPR description, commit (optionally push). `#daily #automation #build`
  Intended to run unattended (e.g. an external nightly cron calling `make update-daily COPR_REPO=... PUSH=1`); the repo itself has no scheduler.
- **COPR-0004** Auto-bump package versions from upstream git tags per each package's update policy. `#versioning #upstream`
- **COPR-0005** Generate RPM spec files from `packages.yaml` and a shared Jinja template. `#packaging #spec`
- **COPR-0006** Test-build packages locally in `mock` before ever touching COPR. `#build #mock #testing`
- **COPR-0007** Submit builds to COPR and push the COPR project description and install docs. `#copr #publish`
- **COPR-0008** Auto-manage RPM `release` numbers: reset on version change, increment on content change, cascade to dependents, lockable. `#packaging #release`
- **COPR-0009** Analyze mock/srpm build logs and surface actionable errors. `#build #diagnostics`
- **COPR-0010** Run a local quality gate — validate, test, lint, format — before and after changes; enforced in CI on every push/PR (lint+test only, no container needed via `NO_CONTAINER=1`) and inside `make update-daily`. `#ci #lint #testing #quality`
- **COPR-0011** Run build/mock/copr automation in a reproducible, privileged Fedora toolbox container per Fedora version, keeping the host clean (lint/test have a native `NO_CONTAINER=1` path, see COPR-0010). `#container #reproducible`
  Runs `--privileged` (required for mock namespaces), with per-Fedora-version persistent volumes for rpmbuild state and the local repo, plus the host's `.venv` mounted in.
- **COPR-0012** Regenerate all docs (README, COPR readme, full report) from the single build-state source of truth. `#docs #reporting`
- **COPR-0013** Manage the package set: list upstream tags, set/lock releases, delete a package cleanly, reset build status. `#packages #maintenance`
- **COPR-0014** Request a new package through a GitHub issue-template form that feeds the add-package automation. `#packages #intake`
- **COPR-0015** Persist all build state in `build-report.db` (sqlite) as the single source of truth: per-stage hash-based caching, per-target (Fedora version) isolation, artifact tracking (SRPM/RPM/vendor tarball) for disk cleanup. `#persistence #state #caching`
- **COPR-0016** Auto-publish the README's branding shell (logo, description, News, Docs, Support, License, People) on every push to `main` or manual dispatch, without needing `build-report.db`. `#ci #docs #publish`
  `scripts/gen-readme-shell.py` splices `__header.j2`/`__footer.j2` into `README.md`/`docs/README.copr.md` between existing marker comments, leaving the packages/build-status body untouched -- CI has no build history to render it from, and this design makes that unnecessary.
