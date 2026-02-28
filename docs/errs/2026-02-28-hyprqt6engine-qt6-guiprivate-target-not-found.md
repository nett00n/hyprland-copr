# Error: hyprqt6engine Qt6::GuiPrivate target not found

`2026-02-28` | `hyprqt6engine` | stage: mock | fc43

## Error

```
CMake Error at hyprqtplugin/CMakeLists.txt:11 (target_link_libraries):
  Target "hyprqtplugin" links to:
    Qt6::GuiPrivate
  but the target was not found.  Possible reasons include:
    * There is a typo in the target name.
    * A find_package call is missing for an IMPORTED target.
    * An ALIAS target is missing.
-- Generating done (0.1s)
CMake Generate step failed.  Build files cannot be regenerated correctly.
```

## Meaning

`Qt6::GuiPrivate` is a CMake INTERFACE target that exposes Qt6's private Gui headers.
It is defined in `Qt6GuiPrivateTargets.cmake`, which is part of `qt6-qtbase-private-devel`.
Having `qt6-qtbase-private-devel` in `BuildRequires` installs the files, but RPM/mock's
`dnf5 builddep` uses CMake capability names (`cmake()` macros) to resolve the actual
package. Without `cmake(Qt6GuiPrivate)` in `BuildRequires`, the private CMake target
files may not be loaded into the CMake find path and the `Qt6::GuiPrivate` target
is never created.

## Fix

Add to `packages.yaml` `build_requires` for `hyprqt6engine`:

```yaml
- cmake(Qt6Gui)
- cmake(Qt6GuiPrivate)
```

`cmake(Qt6Gui)` ensures the public Gui component target is set up.
`cmake(Qt6GuiPrivate)` is what actually provides `Qt6::GuiPrivate`.

## Notes

- `qt6-qtbase-private-devel` alone is not sufficient — use `cmake(Qt6GuiPrivate)` instead
  (or in addition) so the CMake dependency resolver picks it up correctly.
- This class of error only appears at CMake **generate** time (after "Configuring done"),
  not at configure time, which can be confusing.
- The same pattern applies to other Qt6 private components: prefer `cmake(Qt6FooPrivate)`
  over bare `qt6-qtbase-private-devel` in `BuildRequires`.
