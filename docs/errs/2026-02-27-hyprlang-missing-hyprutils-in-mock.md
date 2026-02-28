# Error: hyprlang mock build can't find hyprutils

`2026-02-27` | `hyprlang` | stage: mock | fc43

## Error

```
-- Checking for module 'hyprutils>=0.7.1'
--   Package 'hyprutils' not found
CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:645 (message):
  The following required packages were not found:
   - hyprutils>=0.7.1
```

## Meaning

`hyprutils-devel` was missing from `packages.yaml` for `hyprlang`. It's not in Fedora repos (built locally), and `full-cycle.py` called `mock --rebuild` without exposing locally-built RPMs to the chroot — each mock run starts clean and only sees Fedora repos.

## Fix

**`packages.yaml`:**
```diff
 hyprlang:
   build_requires:
+    - pkgconfig(hyprutils)
```

**`scripts/full-cycle.py`** — after each successful mock build, copy non-SRPM RPMs to `local-repo/` and run `createrepo_c --update`. Pass `--addrepo file://{LOCAL_REPO}` to subsequent mock calls.

## Notes

- All packages that depend on locally-built packages must list them in `packages.yaml`.
- On first run after this fix, force-rebuild: `FORCE_MOCK=1 PACKAGE=hyprutils make build`.
