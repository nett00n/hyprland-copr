# FRD — Feature Requirements

Automation features of this repo, one-liners + tags. Detailed stories live in `docs/features/COPR-NNNN-*.md`.

- **COPR-0001** Add a new package from an upstream URL in one command, registering the git submodule and scaffolding its `packages.yaml` entry. `#packages #onboarding`
- **COPR-0002** Run the full build pipeline (spec → vendor → srpm → mock → copr) for one or all packages with a single command. `#build #pipeline #copr` — [details](features/COPR-0002-full-cycle-build.md)
- **COPR-0003** Run the end-to-end daily update: bump versions, format, build, regenerate docs, push COPR description, commit. `#daily #automation #build` — [details](features/COPR-0003-daily-update.md)
- **COPR-0004** Auto-bump package versions from upstream git tags per each package's update policy. `#versioning #upstream`
- **COPR-0005** Generate RPM spec files from `packages.yaml` and a shared Jinja template. `#packaging #spec`
- **COPR-0006** Test-build packages locally in `mock` before ever touching COPR. `#build #mock #testing`
- **COPR-0007** Submit builds to COPR and push the COPR project description and install docs. `#copr #publish`
- **COPR-0008** Auto-manage RPM `release` numbers: reset on version change, increment on content change, cascade to dependents, lockable. `#packaging #release` — [details](features/COPR-0008-release-autoincrement.md)
- **COPR-0009** Analyze mock/srpm build logs and surface actionable errors. `#build #diagnostics`
- **COPR-0010** Run a local quality gate — validate, test, lint, format — before and after changes. `#ci #lint #testing #quality`
- **COPR-0011** Run all automation in a reproducible, privileged Fedora toolbox container per Fedora version, keeping the host clean. `#container #reproducible` — [details](features/COPR-0011-containerized-runs.md)
- **COPR-0012** Regenerate all docs (README, COPR readme, full report) from the single build-state source of truth. `#docs #reporting`
- **COPR-0013** Manage the package set: list upstream tags, set/lock releases, delete a package cleanly, reset build status. `#packages #maintenance`
- **COPR-0014** Request a new package through a GitHub issue-template form that feeds the add-package automation. `#packages #intake`
- **COPR-0015** Persist all build state in `build-report.db` (sqlite) as the single source of truth: per-stage hash-based caching, per-target (Fedora version) isolation, artifact tracking for disk cleanup. `#persistence #state #caching` — [details](features/COPR-0015-build-state-persistence.md)
