# Error: Qt6 packages wrapped in pkgconfig() macro

`2026-02-28` | `hyprqt6engine`, `xdg-desktop-portal-hyprland` | stage: mock | fc43

## Error

```
Failed to resolve the transaction:
No match for argument: pkgconfig(qt6-qtbase-devel)
No match for argument: pkgconfig(qt6-qtwayland-devel)
```

Seen in the last block of `logs/<pkg>-20-mock.log` during `dnf5 builddep`.

## Meaning

`pkgconfig(foo)` is a RPM dependency macro that resolves to whichever package ships a `foo.pc` pkg-config file. `qt6-qtbase-devel` and `qt6-qtwayland-devel` are RPM package **names**, not pkg-config module names, so wrapping them in `pkgconfig()` produces a dependency that no package satisfies.

## Fix

Use the bare RPM package name without the `pkgconfig()` wrapper:

```spec
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtwayland-devel
```

## Notes

- This mistake is easy to introduce by copy-pasting from adjacent `pkgconfig(hyprlang)` style lines.
- The actual pkg-config module names for Qt6 are things like `Qt6Core`, `Qt6Widgets` — entirely different from the RPM package names.
- The failure surfaces in `<pkg>-20-mock.log` (the `dnf5 builddep` step), **before** `rpmbuild` even starts, so `<pkg>-21-mock-build.log` will be empty or contain only the SRPM header.
