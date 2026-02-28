# Error: aquamarine missing hyprwayland-scanner cmake package

`2026-02-28` | `aquamarine` | stage: mock | fc43

## Error

```
CMake Error at CMakeLists.txt:23 (find_package):
  By not providing "Findhyprwayland-scanner.cmake" in CMAKE_MODULE_PATH this
  project has asked CMake to find a package configuration file provided by
  "hyprwayland-scanner", but CMake did not find one.

  Could not find a package configuration file provided by
  "hyprwayland-scanner" (requested version 0.4.0) with any of the following
  names:
    hyprwayland-scannerConfig.cmake
    hyprwayland-scanner-config.cmake
```

## Meaning

`aquamarine` uses `find_package(hyprwayland-scanner)` in its `CMakeLists.txt`.
The cmake config file is installed by `hyprwayland-scanner-devel`, which was
not listed in `build_requires`, so mock did not install it.

## Fix

Add `hyprwayland-scanner-devel` to `aquamarine.build_requires` in `packages.yaml`.
It cannot be expressed as `pkgconfig(...)` because CMake consumes it via a config
file, not a `.pc` file.

## Notes

- `hyprwayland-scanner-devel` ships `hyprwayland-scannerConfig.cmake` under
  `%{_libdir}/cmake/hyprwayland-scanner/` — already tracked in its own `devel.files`.
- Use the plain `-devel` form (not `pkgconfig()`) for deps consumed via CMake
  `find_package` when no `.pc` file is involved.
