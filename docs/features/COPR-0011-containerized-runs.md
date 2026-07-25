# COPR-0011 — Containerized runs

As a maintainer, all builds run in a container, not on bare host, so the host stays clutter-free.

A Fedora-toolbox-based image is built per supported Fedora version, with `mock`, `copr-cli`, and
build toolchains preinstalled. Runs privileged (required for mock namespaces) with per-version
persistent volumes for rpmbuild state and the local repo, plus the host's `.venv` mounted in.
