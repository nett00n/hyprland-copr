# Error: hyprgraphics 0.1.3 uses wrong Fedora package names

`2026-02-27` | `hyprgraphics` | stage: mock | fc43

## Error

```
Failed to resolve the transaction:
No match for argument: libmagic
No match for argument: spng
```

## Meaning

The spec used upstream pkg-config names instead of Fedora package names. Neither `libmagic` nor `spng` exist as Fedora packages.

## Fix

```diff
 hyprgraphics:
   build_requires:
-    - libmagic
+    - file-devel
-    - spng
+    - pkgconfig(spng)
```

## Notes

- Fedora names differ from upstream: `libmagic` → `file-devel`, `spng` → `libspng-devel`.
- This was superseded by the upgrade to 0.5.0 — see `2026-02-28-hyprgraphics-missing-deps-v0.5.0.md`.
