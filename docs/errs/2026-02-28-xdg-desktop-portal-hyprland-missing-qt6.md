# Error: xdg-desktop-portal-hyprland missing Qt6 BuildRequires

`2026-02-28` | `xdg-desktop-portal-hyprland` | stage: mock | fc43

## Error

```
CMake Error at hyprland-share-picker/CMakeLists.txt:17 (find_package):
  Could not find a package configuration file provided by "QT" with any of
  the following names:
    Qt6Config.cmake
    qt6-config.cmake
  Add the installation prefix of "QT" to CMAKE_PREFIX_PATH or set "QT_DIR" to
  a directory containing one of the above files.  If "QT" provides a separate
  development package or SDK, be sure it has been installed.
-- Configuring incomplete, errors occurred!
RPM build errors:
error: Bad exit status from /var/tmp/rpm-tmp.sfnajk (%build)
```

## Meaning

The `hyprland-share-picker` sub-project (bundled inside `xdg-desktop-portal-hyprland`) uses Qt6 for its GUI. The spec had no `BuildRequires` for Qt6, so mock's clean chroot had no `Qt6Config.cmake` and CMake aborted during configure.

## Fix

Add to the spec's `BuildRequires`:

```spec
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtwayland-devel
```

`qt6-qtbase-devel` ships `Qt6Config.cmake`. `qt6-qtwayland-devel` is needed for Wayland platform integration used by the picker.

## Notes

- The log that contains the actual CMake error is the mock `build.log` (`logs/<pkg>-21-mock-build.log`), not the outer `<pkg>-20-mock.log`.
- Mock runs with `--nodeps` during the `%build` stage, so any missing build-time library must be declared in `BuildRequires` — it won't be pulled in automatically.
