# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-10-29 07:40:54 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 66
- Clean: 64
- With issues: 2
- No logs found: 0
- Copr submission not settled-success: 5

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| glaze | fedora-44-x86_64 | 9.1.0-1.fc44 | unknown | [#11222397](https://copr.fedorainfracloud.org/coprs/build/11222397/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.1-30.fc44 | unknown | [#11222400](https://copr.fedorainfracloud.org/coprs/build/11222400/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-30.fc44 | unknown | [#11222401](https://copr.fedorainfracloud.org/coprs/build/11222401/) | — |
| imageio-ffmpeg | fedora-44-x86_64 | 0.7.0-1.fc44 | unknown | [#11222398](https://copr.fedorainfracloud.org/coprs/build/11222398/) | — |
| waypaper | fedora-44-x86_64 | 2.9-4.fc44 | unknown | [#11222399](https://copr.fedorainfracloud.org/coprs/build/11222399/) | — |

## Issues

### Hyprland (`/work/logs/runs/425/fedora-45-x86_64/Hyprland`)

```

█▓▒░ Mock build issues:
  - missing pkgconfig packages: "libcanberra"
    /work/logs/runs/425/fedora-45-x86_64/Hyprland/21-mock-build.log:195: CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
    suggested packages:
      - "libcanberra-devel"
  - failed during build (%build) — The following required packages were not found:
    /work/logs/runs/425/fedora-45-x86_64/Hyprland/21-mock-build.log:203: error: Bad exit status from /var/tmp/rpm-tmp.hhKEtV (%build)
```

### xdg-desktop-portal-hyprland (`/work/logs/runs/425/fedora-45-x86_64/xdg-desktop-portal-hyprland`)

```

█▓▒░ Mock build issues:
  - missing pkgconfig packages: "hyprtoolkit>=0.6.0"
    /work/logs/runs/425/fedora-45-x86_64/xdg-desktop-portal-hyprland/21-mock-build.log:122: CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
  - failed during build (%build) — The following required packages were not found:
    /work/logs/runs/425/fedora-45-x86_64/xdg-desktop-portal-hyprland/21-mock-build.log:129: error: Bad exit status from /var/tmp/rpm-tmp.ZaUdoO (%build)
```

