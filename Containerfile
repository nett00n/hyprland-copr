# One image builds every SUPPORTED chroot via `mock -r` -- mock does not need a
# matching host, so this is pinned to the newest stable Fedora version (its
# mock-core-configs knows every SUPPORTED chroot, #COPR-0032) rather than
# parameterized per FEDORA_VERSION (Makefile no longer passes a build-arg
# for it; see docs/CHANGELOG.md and docs/FRD.md COPR-0011).
# Digest-pinned (#BUG-0088); refresh deliberately, see COPR-0011 Quirks & Decisions.
FROM registry.fedoraproject.org/fedora-toolbox:45@sha256:0dbcd29c62c476c19dcfb1415f33ca7de12caae9470a67a263487d757278766a

ARG UID=1000
ARG GID=1000
ARG USERNAME=user

RUN dnf install -y -q \
    cargo \
    copr-cli \
    fedpkg \
    git \
    golang \
    mock \
    python3-pip \
    python3-pyyaml \
    python3-virtualenv \
    rpm-build \
    rpmdevtools \
    rpmlint \
    zig \
    && dnf clean all

# Create non-root user with specified UID/GID
RUN groupadd -g "$GID" "$USERNAME" && \
    useradd -m -u "$UID" -g "$GID" -G wheel,mock "$USERNAME" && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel-nopasswd

# Runs on every login shell. Ensures user is in mock group.
COPY docker/mock-group.sh /etc/profile.d/mock-group.sh
RUN chmod 644 /etc/profile.d/mock-group.sh

# Keep root for volume access, but user exists for interactive shells
# USER $UID:$GID
