# Error: hyprgraphics 0.5.0 missing pangocairo and librsvg-2.0 BuildRequires

`2026-02-28` | `hyprgraphics` | stage: mock | fc43

## Error

```
-- Checking for modules 'pixman-1;cairo;pangocairo;hyprutils;libjpeg;libwebp;libmagic;libpng;librsvg-2.0'
--   Package 'pangocairo' not found
--   Package 'hyprutils' not found
--   Package 'libmagic' not found
--   Package 'librsvg-2.0' not found
CMake Error: The following required packages were not found:
 - pangocairo
 - hyprutils
 - libmagic
 - librsvg-2.0
```

## Meaning

`packages.yaml` was written for `hyprgraphics` 0.1.3 and not updated for 0.5.0. Upstream added deps between versions:

| pkg-config name | Fedora package   |
|-----------------|------------------|
| `pangocairo`    | `pango-devel`    |
| `libmagic`      | `file-devel`     |
| `librsvg-2.0`   | `librsvg2-devel` |

`spng` is no longer required in 0.5.0 — remove it.

## Fix

```diff
 hyprgraphics:
   build_requires:
+    - pango-devel
+    - pkgconfig(hyprutils)
+    - file-devel
+    - librsvg2-devel
-    - pkgconfig(spng)
```

## Notes

- When bumping a version, diff the upstream `CMakeLists.txt` between tags to catch added/removed `pkg_check_modules` calls.
- `pangocairo` pkg-config → `pango-devel` (not `pangocairo-devel`).
- `librsvg-2.0` pkg-config → `librsvg2-devel` (note the `2` suffix).
