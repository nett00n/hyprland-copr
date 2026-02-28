# Error: hyprqt6engine Qt6::GuiPrivate not found — missing find_package in upstream

`2026-02-28` | `hyprqt6engine` | stage: mock | fc43

## Error

```
CMake Error at hyprqtplugin/CMakeLists.txt:11 (target_link_libraries):
  Target "hyprqtplugin" links to:
    Qt6::GuiPrivate
  but the target was not found.
CMake Generate step failed.  Build files cannot be regenerated correctly.
```

All Qt6 packages are installed correctly (`qt6-qtbase-devel`, `qt6-qtbase-private-devel`,
`cmake(Qt6GuiPrivate)`, etc.) and `cmake(Qt6GuiPrivate)` correctly resolves to
`qt6-qtbase-private-devel`. The target is still absent.

## Meaning

`hyprqtplugin/CMakeLists.txt` calls `target_link_libraries(hyprqtplugin ... Qt6::GuiPrivate ...)`
but never calls `find_package(Qt6 REQUIRED COMPONENTS GuiPrivate)` first.
In Qt6 CMake, `Qt6::GuiPrivate` is **not** automatically created when `Qt6::Gui` is found —
it requires an explicit component request. This is a bug in the upstream CMakeLists.txt.

The project uses `Qt6BuildInternals` (Qt's own internal build infrastructure), so the
configure phase succeeds and prints `-- Plugin path:` but no `-- Found Qt6::Gui` message,
which is the diagnostic clue.

## Fix

Patch the upstream file in `%prep` via a `prep_commands` entry in `packages.yaml`:

```yaml
prep_commands:
  - "sed -i '/target_link_libraries.*hyprqtplugin/i find_package(Qt6 REQUIRED COMPONENTS GuiPrivate)' hyprqtplugin/CMakeLists.txt"
```

This inserts `find_package(Qt6 REQUIRED COMPONENTS GuiPrivate)` immediately before the
offending `target_link_libraries` call without touching the rest of the file.

## Notes

- Adding `cmake(Qt6GuiPrivate)` to `BuildRequires` is still correct (ensures the package
  is installed), but alone it doesn't fix the issue — the CMakeLists.txt must also call
  `find_package` for that component.
- `prep_commands` support was added to `templates/spec.j2` and `scripts/gen-spec.py`
  to enable inline source patching without separate patch files.
- Drop the workaround once the fix is merged upstream in hyprqt6engine.
