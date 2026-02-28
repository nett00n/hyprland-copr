# Error: Hyprland glaze FetchContent fails in mock (no network)

`2026-03-01` | `Hyprland` | stage: mock | fc43

## Error

First failure — FetchContent tries to clone at build time:

```
[ 22%] Performing download step (git clone) for 'glaze-populate'
Cloning into 'glaze-src'...
fatal: unable to access 'https://github.com/stephenberry/glaze.git/': Could not resolve host: github.com
Had to git clone more than once: 3 times.
```

Second failure — after bundling glaze, `start/` still can't find the header:

```
/builddir/.../start/src/helpers/Nix.cpp:13:10: fatal error: glaze/glaze.hpp: No such file or directory
error: Bad exit status from /var/tmp/rpm-tmp.pXHV7G (%build)
```

## Meaning

Two separate problems with the same root cause (glaze not available as a system package):

1. `hyprpm/CMakeLists.txt` calls `find_package(glaze QUIET)`, fails (glaze is not in Fedora), and falls through to `FetchContent_Declare` which does `git clone`. Mock's chroot has no outbound network.

2. `start/src/helpers/Nix.cpp` unconditionally includes `<glaze/glaze.hpp>`, but `start/CMakeLists.txt` does **not** link against `glaze::glaze` and never declares an include path for it. Worse, the top-level `CMakeLists.txt` does `add_subdirectory(start)` **before** `add_subdirectory(hyprpm)`, so the `glaze::glaze` target created by FetchContent in hyprpm doesn't exist yet when start is configured. This is an upstream bug.

## Fix

**Step 1 — bundle glaze as Source1** so spectool downloads it before the mock build:

In `packages.yaml` (Hyprland entry), add `bundled_deps`:
```yaml
bundled_deps:
  - name: glaze
    version: "7.0.x"
    url: "https://github.com/stephenberry/glaze/archive/refs/tags/v7.0.x.tar.gz"
```

`gen-spec.py` processes `bundled_deps` and generates:
- `%global glaze_version` + `SourceN` in the spec header (via `spec.j2`)
- `tar xf %{SOURCEN}` + `mv glaze-{version} glaze-src` in `%prep`
- `-DFETCHCONTENT_FULLY_DISCONNECTED=ON` and `-DFETCHCONTENT_SOURCE_DIR_GLAZE=...` in the `%cmake` invocation

This fixes the FetchContent clone attempt. `hyprpm` compiles correctly once glaze-src is in place.

**Step 2 — patch `start/CMakeLists.txt`** to add the glaze include path before cmake processes that subdirectory:

In `packages.yaml` (Hyprland entry), add `prep_commands`:
```yaml
prep_commands:
  - "sed -i 's|^install(TARGETS start-hyprland)|target_include_directories(start-hyprland PRIVATE \"${CMAKE_CURRENT_SOURCE_DIR}/../glaze-src/include\")\\ninstall(TARGETS start-hyprland)|' start/CMakeLists.txt"
```

This inserts a `target_include_directories` call using cmake's own `${CMAKE_CURRENT_SOURCE_DIR}` so the path is resolved at configure time — no RPM macros, no hardcoded absolute paths.

## Notes

- `FETCHCONTENT_FULLY_DISCONNECTED=ON` prevents CMake from ever attempting network access even when a source dir override is set — belt-and-suspenders.
- The `#/glaze-{version}.tar.gz` fragment in the Source URL gives spectool/rpmbuild a stable local filename, avoiding collision with the main `v{version}.tar.gz` download.
- `glaze` is header-only; no linking is needed, only the include path.
- The `start/` patch is an upstream bug workaround. Watch for it being fixed upstream (proper `target_link_libraries` in `start/CMakeLists.txt` or glaze FetchContent moved to the top-level before `add_subdirectory(start)`).
- Keep `bundled_deps.version` and `url` in sync — mismatching them causes `mv glaze-{version} glaze-src` to fail in `%prep` because the GitHub tarball extracts to the tag version, not the declared version.
