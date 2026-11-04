# Nightly log analysis summary

## Upstream version refresh

_Generated 2026-11-04 09:06:08 UTC by `make update-versions`._

1 failure(s):

### pin

- `LukashonakV/cava`: pinned by libcava-v0 (pinned-tag with no auto_update.tag); leaving the checkout untouched

- Packages analyzed: 66
- Clean: 59
- With issues: 7
- No logs found: 0
- Copr submission not settled-success: 7

## Copr submission

Rows below have a build-report.db `copr` state that isn't `success`/`skipped` -- includes a genuine build failure as well as a submission still pending/unresolved (e.g. a watch that hit `CMD_TIMEOUT`, see #BUG-0107); check the build_id link before treating one as a real failure.

| Package | Target | Version | State | Build | Reason |
|:--------|:-------|:--------|:------|:------|:-------|
| Hyprland | fedora-44-x86_64 | 0.57.1-1.fc44 | unknown | [#11254732](https://copr.fedorainfracloud.org/coprs/build/11254732/) | — |
| hyprland-guiutils | fedora-44-x86_64 | 0.2.2-18.fc44 | failed | [#11254735](https://copr.fedorainfracloud.org/coprs/build/11254735/) | — |
| hyprlauncher | fedora-44-x86_64 | 0.1.7-3.fc44 | failed | [#11254734](https://copr.fedorainfracloud.org/coprs/build/11254734/) | — |
| hyprpaper | fedora-44-x86_64 | 0.8.5-1.fc44 | failed | [#11254733](https://copr.fedorainfracloud.org/coprs/build/11254733/) | — |
| hyprpwcenter | fedora-44-x86_64 | 0.1.2-24.fc44 | failed | [#11254736](https://copr.fedorainfracloud.org/coprs/build/11254736/) | — |
| hyprshutdown | fedora-44-x86_64 | 0.1.2-1.fc44 | failed | [#11254737](https://copr.fedorainfracloud.org/coprs/build/11254737/) | — |
| hyprsysteminfo | fedora-44-x86_64 | 0.2.0-31.fc44 | failed | [#11254738](https://copr.fedorainfracloud.org/coprs/build/11254738/) | — |

## Issues

### hyprland-guiutils (`/work/logs/runs/464/fedora-44-x86_64/hyprland-guiutils`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprland-plugins (`/work/logs/runs/455/fedora-45-x86_64/hyprland-plugins`)

```

█▓▒░ Mock build issues:
  - header not found: "hyprland/src/desktop/view/Window.hpp" — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:168: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/borderDeco.cpp:6:10: fatal error: hyprland/src/desktop/view/Window.hpp: No such file or directory
  - header not found: "hyprland/src/desktop/view/Window.hpp" — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:175: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/csgo-vulkan-fix/main.cpp:8:10: fatal error: hyprland/src/desktop/view/Window.hpp: No such file or directory
  - header not found: "hyprland/src/desktop/view/Window.hpp" — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:182: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/barDeco.cpp:8:10: fatal error: hyprland/src/desktop/view/Window.hpp: No such file or directory
  - header not found: "hyprland/src/desktop/view/Window.hpp" — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:189: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/main.cpp:8:10: fatal error: hyprland/src/desktop/view/Window.hpp: No such file or directory
  - compilation error (line 16): ‘virtual std::vector<Hyprutils::Memory::CUniquePointer<IPassElement> > CBorderPPPassElement::draw()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:197: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/BorderppPassElement.hpp:16:43: error: ‘virtual std::vector<Hyprutils::Memory::CUniquePointer<IPassElement> > CBorderPPPassElement::draw()’ marked ‘override’, but does not override
  - compilation error (line 17): ‘virtual bool CBorderPPPassElement::needsLiveBlur()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:200: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/BorderppPassElement.hpp:17:43: error: ‘virtual bool CBorderPPPassElement::needsLiveBlur()’ marked ‘override’, but does not override
  - compilation error (line 18): ‘virtual bool CBorderPPPassElement::needsPrecomputeBlur()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:203: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/BorderppPassElement.hpp:18:43: error: ‘virtual bool CBorderPPPassElement::needsPrecomputeBlur()’ marked ‘override’, but does not override
  - compilation error (line 11): struct/class has no such member — incompatible dependency version or API mismatch
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:207: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/borders-plus-plus/BorderppPassElement.cpp:11:42: error: ‘class Render::IHyprRenderer’ has no member named ‘m_renderData’
  - compilation error (line 16): ‘virtual std::vector<Hyprutils::Memory::CUniquePointer<IPassElement> > CBarPassElement::draw()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:214: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.hpp:16:43: error: ‘virtual std::vector<Hyprutils::Memory::CUniquePointer<IPassElement> > CBarPassElement::draw()’ marked ‘override’, but does not override
  - compilation error (line 17): ‘virtual bool CBarPassElement::needsLiveBlur()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:217: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.hpp:17:43: error: ‘virtual bool CBarPassElement::needsLiveBlur()’ marked ‘override’, but does not override
  - compilation error (line 18): ‘virtual bool CBarPassElement::needsPrecomputeBlur()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:220: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.hpp:18:43: error: ‘virtual bool CBarPassElement::needsPrecomputeBlur()’ marked ‘override’, but does not override
  - compilation error (line 19): ‘virtual std::optional<Hyprutils::Math::CBox> CBarPassElement::boundingBox()’ marked ‘override’, but does not override
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:223: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.hpp:19:43: error: ‘virtual std::optional<Hyprutils::Math::CBox> CBarPassElement::boundingBox()’ marked ‘override’, but does not override
  - compilation error (line 13): struct/class has no such member — incompatible dependency version or API mismatch
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:227: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.cpp:13:44: error: ‘class Render::IHyprRenderer’ has no member named ‘m_renderData’
  - compilation error (line 29): struct/class has no such member — incompatible dependency version or API mismatch
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:231: /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.cpp:29:71: error: ‘class Render::IHyprRenderer’ has no member named ‘m_renderData’
  - failed during build (%build) — /builddir/build/BUILD/hyprland-plugins-0.56.0_20260805git00862ca-build/hyprland-plugins-00862ca3e2908857f9660adbba1b2d55796aaa43/hyprbars/BarPassElement.cpp:29:71: error: ‘class Render::IHyprRenderer’ has no member named ‘m_renderData’
    /work/logs/runs/455/fedora-45-x86_64/hyprland-plugins/21-mock-build.log:235: error: Bad exit status from /var/tmp/rpm-tmp.qTOhHt (%build)
```

### hyprlauncher (`/work/logs/runs/464/fedora-44-x86_64/hyprlauncher`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpaper (`/work/logs/runs/464/fedora-44-x86_64/hyprpaper`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprpwcenter (`/work/logs/runs/464/fedora-44-x86_64/hyprpwcenter`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprshutdown (`/work/logs/runs/464/fedora-44-x86_64/hyprshutdown`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

### hyprsysteminfo (`/work/logs/runs/464/fedora-44-x86_64/hyprsysteminfo`)

```

█▓▒░ COPR chroot mismatch:
  - failed on fedora-43-aarch64 only (7 succeeded: fedora-45-x86_64, fedora-44-x86_64, fedora-44-aarch64, fedora-43-x86_64, fedora-45-aarch64, fedora-rawhide-aarch64, fedora-rawhide-x86_64) — release/toolchain-specific breakage, consider an os_overrides skip in packages.yaml
```

