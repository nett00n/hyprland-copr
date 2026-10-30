# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-10-30 11:15:03 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 66
- Clean: 64
- With issues: 2
- No logs found: 0
- Copr submission not settled-success: 0

## Issues

### Hyprland (`/work/logs/runs/433/fedora-45-x86_64/Hyprland`)

```

█▓▒░ Mock build issues:
  - missing pkgconfig packages: "libcanberra"
    /work/logs/runs/433/fedora-45-x86_64/Hyprland/21-mock-build.log:195: CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
    suggested packages:
      - "libcanberra-devel"
  - failed during build (%build) — The following required packages were not found:
    /work/logs/runs/433/fedora-45-x86_64/Hyprland/21-mock-build.log:202: error: Bad exit status from /var/tmp/rpm-tmp.CwIgT3 (%build)
```

### xdg-desktop-portal-hyprland (`/work/logs/runs/433/fedora-45-x86_64/xdg-desktop-portal-hyprland`)

```

█▓▒░ Mock build issues:
  - missing pkgconfig packages: "hyprtoolkit>=0.6.0"
    /work/logs/runs/433/fedora-45-x86_64/xdg-desktop-portal-hyprland/21-mock-build.log:122: CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
  - failed during build (%build) — The following required packages were not found:
    /work/logs/runs/433/fedora-45-x86_64/xdg-desktop-portal-hyprland/21-mock-build.log:129: error: Bad exit status from /var/tmp/rpm-tmp.A2yDQf (%build)
```

