ARG FEDORA_VERSION=43

FROM registry.fedoraproject.org/fedora-toolbox:${FEDORA_VERSION}

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
