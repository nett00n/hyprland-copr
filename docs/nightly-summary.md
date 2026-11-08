# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-11-08 10:29:11 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 73
- Clean: 66
- With issues: 6
- No logs found: 1
- Copr submission not settled-success: 6

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| hyprland-guiutils | fedora-44-x86_64 | 0.2.2-18.fc44 | failed | [#11286979](https://copr.fedorainfracloud.org/coprs/build/11286979/) | — |
| hyprlauncher | fedora-44-x86_64 | 0.1.7-3.fc44 | failed | [#11286983](https://copr.fedorainfracloud.org/coprs/build/11286983/) | — |
| hyprpaper | fedora-44-x86_64 | 0.8.5-1.fc44 | failed | [#11286980](https://copr.fedorainfracloud.org/coprs/build/11286980/) | — |
| hyprpwcenter | fedora-44-x86_64 | 0.1.2-24.fc44 | failed | [#11286982](https://copr.fedorainfracloud.org/coprs/build/11286982/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.2-1.fc44 | failed | [#11286981](https://copr.fedorainfracloud.org/coprs/build/11286981/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-31.fc44 | failed | [#11286978](https://copr.fedorainfracloud.org/coprs/build/11286978/) | — |

## Issues

### hyprland-guiutils (`/work/logs/runs/500/fedora-44-x86_64/hyprland-guiutils`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprlauncher (`/work/logs/runs/500/fedora-44-x86_64/hyprlauncher`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64, fedora-rawhide-aarch64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpaper (`/work/logs/runs/500/fedora-44-x86_64/hyprpaper`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpwcenter (`/work/logs/runs/500/fedora-44-x86_64/hyprpwcenter`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprshutdown (`/work/logs/runs/500/fedora-44-x86_64/hyprshutdown`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprsysteminfo (`/work/logs/runs/500/fedora-44-x86_64/hyprsysteminfo`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

## No logs found

- hyprland-plugins

