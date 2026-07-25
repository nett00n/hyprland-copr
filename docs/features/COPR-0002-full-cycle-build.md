# COPR-0002 — Full-cycle build pipeline

As a maintainer, I run one command to take a package from spec to a submitted COPR build.

The pipeline chains: generate spec → vendor deps (Go only) → build SRPM → test-build in mock →
submit to COPR. Each stage is individually skippable/forceable and results are cached by
content hash, so unchanged packages are skipped on rerun. Works for one package or all of them.
