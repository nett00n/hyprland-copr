# Error: File must begin with "/" — null entry in %files

`2026-02-28` | `aquamarine`, `hyprtoolkit` | stage: mock | fc43

## Error

```
error: File must begin with "/": None
RPM build errors:
    File must begin with "/": None
Child return code was: 1
```

## Meaning

In `packages.yaml`, a list item written as `- # FIXME: add installed files`
(a `-` followed only by a comment) is valid YAML but evaluates to `null` (Python
`None`). The spec generator passed that `None` through to the `%files` section,
rendering it literally as the string `None`, which RPM rejected.

## Fix

1. **`packages.yaml`**: Change `- # comment` to `# comment` (plain comment, not
   a list item) for any `files` entry that has no real path yet:
   ```yaml
   # before (creates a null list item):
   - # FIXME: add installed files

   # after (plain YAML comment, ignored by parser):
   # FIXME: add installed files
   ```

2. **`gen-spec.py`**: Added a defensive `None` filter when building the `files`
   and `devel.files` / `devel.requires` lists in `build_context()`, so a stray
   null can never reach the rendered spec again.

## Notes

- Affected packages: `aquamarine` and `hyprtoolkit` (both had placeholder
  `files` entries with the same pattern).
- YAML `- # comment` and `- ` (bare dash with no value) both produce `null`.
  Use a plain `# comment` line instead when no path is known yet.
