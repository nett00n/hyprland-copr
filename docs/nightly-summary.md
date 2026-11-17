# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-11-17 12:07:47 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 73
- Clean: 64
- With issues: 7
- No logs found: 2
- Copr submission not settled-success: 6

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| hyprland-guiutils | fedora-44-x86_64 | 0.2.2-19.fc44 | failed | [#11340381](https://copr.fedorainfracloud.org/coprs/build/11340381/) | — |
| hyprlauncher | fedora-44-x86_64 | 0.1.7-4.fc44 | failed | [#11340380](https://copr.fedorainfracloud.org/coprs/build/11340380/) | — |
| hyprpaper | fedora-44-x86_64 | 0.8.5-1.fc44 | failed | [#11340382](https://copr.fedorainfracloud.org/coprs/build/11340382/) | — |
| hyprpwcenter | fedora-44-x86_64 | 0.1.2-25.fc44 | failed | [#11340383](https://copr.fedorainfracloud.org/coprs/build/11340383/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.2-2.fc44 | failed | [#11340385](https://copr.fedorainfracloud.org/coprs/build/11340385/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-32.fc44 | failed | [#11340384](https://copr.fedorainfracloud.org/coprs/build/11340384/) | — |

## Issues

### hyprland-guiutils (`/work/logs/runs/526/fedora-44-x86_64/hyprland-guiutils`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-44-x86_64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprlauncher (`/work/logs/runs/526/fedora-44-x86_64/hyprlauncher`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64, fedora-44-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpaper (`/work/logs/runs/526/fedora-44-x86_64/hyprpaper`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-44-x86_64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpwcenter (`/work/logs/runs/526/fedora-44-x86_64/hyprpwcenter`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-44-x86_64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprshutdown (`/work/logs/runs/526/fedora-44-x86_64/hyprshutdown`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-44-x86_64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprsysteminfo (`/work/logs/runs/526/fedora-44-x86_64/hyprsysteminfo`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-44-x86_64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### waylock (`/work/logs/runs/525/fedora-45-x86_64/waylock`)

```

█▓▒░ Mock build issues:
  - compilation error (line 26): member function expected 2 argument(s), found 1
    /work/logs/runs/525/fedora-45-x86_64/waylock/21-mock-build.log:89: build.zig:26:16: error: member function expected 2 argument(s), found 1
  - failed during build (%build) — build.zig:26:16: error: member function expected 2 argument(s), found 1
    /work/logs/runs/525/fedora-45-x86_64/waylock/21-mock-build.log:99: error: Bad exit status from /var/tmp/rpm-tmp.lZi678 (%build)
```

## No logs found

- bare
- hyprland-plugins

