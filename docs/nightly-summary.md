# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-11-07 08:04:50 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 73
- Clean: 66
- With issues: 6
- No logs found: 1
- Copr submission not settled-success: 7

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| Hyprland | fedora-44-x86_64 | 0.57.1-2.fc44 | unknown | [#11283255](https://copr.fedorainfracloud.org/coprs/build/11283255/) | — |
| hyprland-guiutils | fedora-44-x86_64 | 0.2.2-18.fc44 | failed | [#11283257](https://copr.fedorainfracloud.org/coprs/build/11283257/) | — |
| hyprlauncher | fedora-44-x86_64 | 0.1.7-3.fc44 | failed | [#11283258](https://copr.fedorainfracloud.org/coprs/build/11283258/) | — |
| hyprpaper | fedora-44-x86_64 | 0.8.5-1.fc44 | failed | [#11283256](https://copr.fedorainfracloud.org/coprs/build/11283256/) | — |
| hyprpwcenter | fedora-44-x86_64 | 0.1.2-24.fc44 | failed | [#11283261](https://copr.fedorainfracloud.org/coprs/build/11283261/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.2-1.fc44 | failed | [#11283259](https://copr.fedorainfracloud.org/coprs/build/11283259/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-31.fc44 | failed | [#11283260](https://copr.fedorainfracloud.org/coprs/build/11283260/) | — |

## Issues

### hyprland-guiutils (`/work/logs/runs/489/fedora-44-x86_64/hyprland-guiutils`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprlauncher (`/work/logs/runs/489/fedora-44-x86_64/hyprlauncher`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpaper (`/work/logs/runs/489/fedora-44-x86_64/hyprpaper`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpwcenter (`/work/logs/runs/489/fedora-44-x86_64/hyprpwcenter`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprshutdown (`/work/logs/runs/489/fedora-44-x86_64/hyprshutdown`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprsysteminfo (`/work/logs/runs/489/fedora-44-x86_64/hyprsysteminfo`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

## No logs found

- hyprland-plugins

