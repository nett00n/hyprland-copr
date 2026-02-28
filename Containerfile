ARG FEDORA_VERSION=43
FROM registry.fedoraproject.org/fedora-toolbox:${FEDORA_VERSION}

RUN sudo dnf install -y \
    copr-cli \
    fedpkg \
    git \
    mock \
    python3-pip \
    python3-pyyaml \
    python3-virtualenv \
    rpm-build \
    rpmdevtools \
    rpmlint \
    && sudo dnf clean all

# Runs on every login shell. On first enter: adds user to mock group and
# replaces the current shell via exec so the group is active immediately.
# On subsequent enters: check passes silently.
RUN tee /etc/profile.d/mock-group.sh > /dev/null << 'EOF'
#!/bin/bash
if ! id -nG "${USER}" 2>/dev/null | grep -qw mock; then
    sudo usermod -aG mock "${USER}" 2>/dev/null
    exec newgrp mock
fi
EOF
