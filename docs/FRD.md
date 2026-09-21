# FRD — Feature Requirements Document

Automation features of this repo. See `docs/DOCS-DRIVEN-DEVELOPMENT.md` for how this
file and `docs/features/` work together.

## Available Features

- [X] [COPR-0001. Add a new package from an upstream URL](features/COPR-0001-add-package-from-url.md) - `#packages` `#onboarding`
- [X] [COPR-0002. Full build pipeline (spec → vendor → srpm → mock → copr)](features/COPR-0002-full-build-pipeline.md) - `#build` `#pipeline` `#copr`
- [X] [COPR-0003. Daily update automation](features/COPR-0003-daily-update.md) - `#daily` `#automation` `#build`
- [X] [COPR-0004. Auto-bump package versions from upstream](features/COPR-0004-version-auto-bump.md) - `#versioning` `#upstream`
- [X] [COPR-0005. Generate RPM spec files from packages.yaml](features/COPR-0005-spec-generation.md) - `#packaging` `#spec`
- [X] [COPR-0006. Test-build packages locally in mock](features/COPR-0006-local-mock-builds.md) - `#build` `#mock` `#testing`
- [X] [COPR-0007. Submit builds to Copr](features/COPR-0007-copr-submission.md) - `#copr` `#publish`
- [X] [COPR-0008. Auto-manage RPM release numbers](features/COPR-0008-release-numbering.md) - `#packaging` `#release`
- [X] [COPR-0009. Analyze build logs and surface actionable errors](features/COPR-0009-log-analysis.md) - `#build` `#diagnostics`
- [X] [COPR-0010. Local quality gate (validate, test, lint, format)](features/COPR-0010-quality-gate.md) - `#ci` `#lint` `#testing` `#quality`
- [X] [COPR-0011. Reproducible toolbox container for build automation](features/COPR-0011-toolbox-container.md) - `#container` `#reproducible`
- [X] [COPR-0012. Regenerate docs from the build-state source of truth](features/COPR-0012-docs-generation.md) - `#docs` `#reporting`
- [X] [COPR-0013. Manage the package set](features/COPR-0013-package-set-management.md) - `#packages` `#maintenance`
- [X] [COPR-0014. Request a new package via GitHub issue](features/COPR-0014-package-request-intake.md) - `#packages` `#intake`
- [X] [COPR-0015. Persist build state in build-report.db](features/COPR-0015-build-state-db.md) - `#persistence` `#state` `#caching`
- [X] [COPR-0016. Auto-publish the README branding shell in CI](features/COPR-0016-readme-shell-publish.md) - `#ci` `#docs` `#publish`
- [X] [COPR-0017. Build every supported chroot locally before submitting once](features/COPR-0017-chroot-matrix-build.md) - `#build` `#matrix` `#copr`
- [X] [COPR-0018. Generate the spec and SRPM once, reuse across every chroot](features/COPR-0018-single-spec-single-srpm.md) - `#build` `#matrix` `#spec` `#srpm`
- [ ] [COPR-0019. Distro/arch-agnostic build target](features/COPR-0019-build-target.md) - `#matrix` `#build`
- [ ] [COPR-0020. aarch64 local build support](features/COPR-0020-aarch64-local-builds.md) - `#matrix` `#build` `#arch`
- [ ] [COPR-0021. Per-chroot Copr rows and a package × target matrix report](features/COPR-0021-copr-chroot-matrix.md) - `#matrix` `#copr` `#reporting`
- [X] [COPR-0022. Run-scoped logs and a durable nightly summary](features/COPR-0022-run-scoped-logs-and-summary.md) - `#daily` `#diagnostics` `#logs`
- [ ] [COPR-0023. Upstream source signature verification](features/COPR-0023-source-signature-verification.md) - `#security` `#provenance`
- [ ] [COPR-0024. Agent memory via HyperMnesia (Tier 0/1 constraints + doc search)](features/COPR-0024-hypermnesia-memory.md) - `#tooling` `#docs` `#agents`

## Tags

- `#agents`: COPR-0024
- `#arch`: COPR-0020
- `#automation`: COPR-0003
- `#build`: COPR-0002, COPR-0003, COPR-0006, COPR-0009, COPR-0017, COPR-0018, COPR-0019, COPR-0020
- `#caching`: COPR-0015
- `#ci`: COPR-0010, COPR-0016
- `#container`: COPR-0011
- `#copr`: COPR-0002, COPR-0007, COPR-0017, COPR-0021
- `#daily`: COPR-0003, COPR-0022
- `#diagnostics`: COPR-0009, COPR-0022
- `#docs`: COPR-0012, COPR-0016, COPR-0024
- `#intake`: COPR-0014
- `#lint`: COPR-0010
- `#logs`: COPR-0022
- `#maintenance`: COPR-0013
- `#matrix`: COPR-0017, COPR-0018, COPR-0019, COPR-0020, COPR-0021
- `#mock`: COPR-0006
- `#onboarding`: COPR-0001
- `#packages`: COPR-0001, COPR-0013, COPR-0014
- `#packaging`: COPR-0005, COPR-0008
- `#persistence`: COPR-0015
- `#pipeline`: COPR-0002
- `#provenance`: COPR-0023
- `#publish`: COPR-0007, COPR-0016
- `#quality`: COPR-0010
- `#release`: COPR-0008
- `#reporting`: COPR-0012, COPR-0021
- `#reproducible`: COPR-0011
- `#security`: COPR-0023
- `#spec`: COPR-0005, COPR-0018
- `#srpm`: COPR-0018
- `#state`: COPR-0015
- `#testing`: COPR-0006, COPR-0010
- `#tooling`: COPR-0024
- `#upstream`: COPR-0004
- `#versioning`: COPR-0004
