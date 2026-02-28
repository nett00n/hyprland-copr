# Error: devel subpackage references cmake/ dir that upstream does not install

`2026-02-28` | `hyprlang`, `hyprgraphics` | stage: mock | fc43

## Error

```
Processing files: hyprlang-devel-0.6.8-1.fc43.fc43.x86_64
error: Directory not found: /builddir/.../BUILDROOT/usr/lib64/cmake/hyprlang

Processing files: hyprgraphics-devel-0.5.0-1.fc43.fc43.x86_64
error: Directory not found: /builddir/.../BUILDROOT/usr/lib64/cmake/hyprgraphics
```

## Meaning

`packages.yaml` listed `%{_libdir}/cmake/<name>/` in `devel.files`, but these packages only ship a `.pc` file — no cmake config directory is installed by upstream.

## Fix

```diff
 hyprlang:
   devel:
     files:
-      - "%{_libdir}/cmake/hyprlang/"

 hyprgraphics:
   devel:
     files:
-      - "%{_libdir}/cmake/hyprgraphics/"
```

## Notes

- Before adding a cmake dir to `devel.files`, check the upstream `CMakeLists.txt` for `install(EXPORT ...)` or `install(FILES ...Config.cmake)`. If there's only `install(TARGETS ...)` + a `.pc.in` file, there's no cmake dir.
