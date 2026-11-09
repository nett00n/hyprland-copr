# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-11-09 06:50:38 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 73
- Clean: 64
- With issues: 8
- No logs found: 1
- Copr submission not settled-success: 10

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| Hyprland | fedora-44-x86_64 | 0.57.1-3.fc44 | unknown | [#11290918](https://copr.fedorainfracloud.org/coprs/build/11290918/) | — |
| hyprland-guiutils | fedora-44-x86_64 | 0.2.2-19.fc44 | failed | [#11290922](https://copr.fedorainfracloud.org/coprs/build/11290922/) | — |
| hyprlauncher | fedora-44-x86_64 | 0.1.7-4.fc44 | failed | [#11290920](https://copr.fedorainfracloud.org/coprs/build/11290920/) | — |
| hyprpaper | fedora-44-x86_64 | 0.8.5-1.fc44 | failed | [#11290927](https://copr.fedorainfracloud.org/coprs/build/11290927/) | — |
| hyprpwcenter | fedora-44-x86_64 | 0.1.2-25.fc44 | failed | [#11290925](https://copr.fedorainfracloud.org/coprs/build/11290925/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.2-2.fc44 | failed | [#11290928](https://copr.fedorainfracloud.org/coprs/build/11290928/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-32.fc44 | failed | [#11290921](https://copr.fedorainfracloud.org/coprs/build/11290921/) | — |
| ironbar | fedora-44-x86_64 | 0.19.1-2.fc44 | unknown | [#11290912](https://copr.fedorainfracloud.org/coprs/build/11290912/) | — |
| SwayOSD | fedora-44-x86_64 | 0.3.2-7.fc44 | unknown | [#11290908](https://copr.fedorainfracloud.org/coprs/build/11290908/) | — |
| Waybar | fedora-44-x86_64 | 0.16.0-3.fc44 | unknown | [#11290916](https://copr.fedorainfracloud.org/coprs/build/11290916/) | — |

## Issues

### hyprland-guiutils (`/work/logs/runs/504/fedora-44-x86_64/hyprland-guiutils`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprlauncher (`/work/logs/runs/504/fedora-44-x86_64/hyprlauncher`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpaper (`/work/logs/runs/504/fedora-44-x86_64/hyprpaper`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpwcenter (`/work/logs/runs/504/fedora-44-x86_64/hyprpwcenter`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprshutdown (`/work/logs/runs/504/fedora-44-x86_64/hyprshutdown`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprsunset (`/work/logs/runs/503/fedora-45-x86_64/hyprsunset`)

```

█▓▒░ Mock build issues:
  - RPM macro "%{_userunitdir}/hyprsunset.service" not expanded — add package providing macro to build_requires (e.g., systemd-rpm-macros for %{_userunitdir})
    /work/logs/runs/503/fedora-45-x86_64/hyprsunset/21-mock-build.log:238: error: File must begin with "/": %{_userunitdir}/hyprsunset.service
```

### hyprsysteminfo (`/work/logs/runs/504/fedora-44-x86_64/hyprsysteminfo`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-rawhide-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### neowall (`/work/logs/runs/503/fedora-45-x86_64/neowall`)

```

█▓▒░ Mock build issues:
  - RPM macro "%{_userunitdir}/neowall.service" not expanded — add package providing macro to build_requires (e.g., systemd-rpm-macros for %{_userunitdir})
    /work/logs/runs/503/fedora-45-x86_64/neowall/21-mock-build.log:392: error: File must begin with "/": %{_userunitdir}/neowall.service
```

## No logs found

- hyprland-plugins

