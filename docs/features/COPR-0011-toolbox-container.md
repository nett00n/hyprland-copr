# COPR-0011. Reproducible toolbox container for build automation

**Tags:** #container #reproducible

## User Story

As a maintainer, I want build/mock/copr automation to run in one reproducible,
privileged container, so that the host stays clean and every supported Fedora chroot
builds the same way regardless of what's installed locally.

## Behavior

A single, version-independent container image (pinned to the oldest supported Fedora
version) runs `mock -r` for every chroot in `SUPPORTED_FEDORA_VERSIONS` — `mock -r`
doesn't need a matching host, so one image builds every chroot. Runs `--privileged`
(required for mock namespaces). A shared `rpmbuild` podman volume persists across every
`FEDORA_VERSION` in the same container (one `~/rpmbuild`), which is what makes "one
spec, one SRPM" (COPR-0018) true by construction. Mock's own buildroot cache/root
volumes stay per-`FEDORA_VERSION`, since mock already namespaces those internally.
`lint`/`test` have a native `NO_CONTAINER=1` path that doesn't need the container at
all (used by CI, which can't nest privileged containers).

## Implementation

- `Containerfile`.
- `Makefile` `CONTAINER_RUN`/`container-build`/`container-enter`/`container-clean`/
  `container-volume-clean`/`check-image`.

## Quirks & Decisions

- Decision: the base image is digest-pinned (`fedora-toolbox:43@sha256:...`) so the
  image is reproducible; the tag stays for readability. Individual dnf packages are
  deliberately not pinned -- against a floating base that only produces resolution
  failures. Refresh the digest deliberately when the base should move
  (`podman pull` the tag, then `podman image inspect --format '{{.Digest}}'`). (BUG-0088)

## Testing

### Integration

- `tests/integration/test_make_targets.py` exercises container-dependent targets via
  `make -n` / `NO_CONTAINER=1`.

## Status

Implemented
