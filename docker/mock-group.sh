#!/bin/bash
if ! id -nG "${USER}" 2>/dev/null | grep -qw mock; then
    sudo usermod -aG mock "${USER}" 2>/dev/null
    exec newgrp mock
fi
