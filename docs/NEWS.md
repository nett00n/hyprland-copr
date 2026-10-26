# News

Maintainer's microblog, informal, about the packages: added, removed, updated or fixed
packages and which Fedora versions are built. Changes to the automation itself go to
`docs/CHANGELOG.md`. Newest first, dated `## YYYY-MM-DD` entries, one short paragraph each.
README shows the most recent entries - see `scripts/lib/readme_content.py:get_recent_news()`.

## 2026-10-26

Added Packages:

- greyline - Live world-time desktop wallpaper with a day/night terminator
- hellwal - Fast, extensible color palette generator
- matugen - Material You and base16 color generation tool with templates
- pywal - Generate and change color-schemes on the fly (original, archived upstream)
- pywal16 - Maintained pywal fork; conflicts with pywal
- usbtree - Live USB device tree in your terminal

## 2026-10-22
Zig-based packages are now supported: the build system and the vendoring of `build.zig.zon` dependencies are automated like Go and Rust.

Added Packages:

- swaylock-effects - Swaylock fork with fancy effects (blur, clock, fade-in)
- swaylock-plugin - Swaylock fork that can use a Wayland client as lock screen background
- waylock - Small screenlocker for Wayland compositors

## 2026-10-21

Added Packages:

- neowall - GPU-accelerated live wallpaper engine using GLSL shaders

## 2026-10-12

Added Packages:

- wl-clip-persist - Keep Wayland clipboard even after programs close
- OpenLogi - Local-first alternative to Logitech Options+ for HID++ devices. Partial build: only the CLI and the background agent (systemd user unit) are packaged. The GPUI desktop window and the on-screen overlay are not built, because they depend on crates published only as git sources (gpui-kit, appicon), which cannot be vendored for offline COPR builds

## 2026-09-17

Added Packages:

- LambDock - Wayland desktop dock customizable with GNU Guile Scheme
- SwayOSD - GTK based on screen display for keyboard shortcuts like caps-lock and volume

## 2026-08-10

Added Packages:

- Ironbar - Customisable Wayland GTK4 bar written in Rust

## 2026-08-09

Fixed packages:

- screeninfo - was not built successfully on fedora 43 - automation fix
- quickshell - was not built successfully on fedora 43 - additional flag in build process
- Hyprland - was not built sucessfully on fedora 43 - applied LionHeartP's patch. It builds locally but copr still fails

## 2026-08-05

Added Packages:

- waypaper - GUI wallpaper manager for Wayland and Xorg
- imageio-ffmpeg - FFMPEG wrapper for Python (waypaper dependency)

## 2026-08-02

I understood that i've added `*-git` packages just to match solopasha's repo and i did not understand how hard it would really be. `*-git` packages are removed from repo for now. Maybe i would get back to it in future, bit that's not a promise.

The vendoring process is reworked.

Removed packages:
- cava - already present in fedora 43, 44, 45
- hyprland-git
- hyprland-plugins-git
- waybar-git

Added packages:
- libcava - same cava, but built as shared library only (fork of cava providing it as a shared library)
- satty - Modern screenshot annotation tool

Updated packages:
- Waybar - now built with cava support

## 2026-08-01

Added Packages:

- mpvpaper - Video wallpaper program for wlroots based Wayland compositors
- snappy-switcher - Alt-tab window switcher for Wayland compositors

Big automation update. SQLite is now used to store build-related info instead of plain yaml file.
Not so simple, but yaml was really messed up and limits architechture.
## 2026-06-30

New packages:
- snappy-switcher - Alt-tab window switcher for Wayland compositors
- mpvpaper - Video wallpaper program for wlroots based Wayland compositors

Added a `recommends` field to package config.

## 2026-06-11

Added Packages:

- eww - Elkowars Wacky Widgets, a standalone widget system in Rust for custom widgets in any window manager

## 2026-05-19

Added Packages:

- hyprland-per-window-layout - Per-window keyboard layout daemon for Hyprland (first successful Rust build)

## 2026-04-24

`release` a thing now, and shows real counter of builds for current version of package. The most ofthen cause of rebuild would be the dependency version update.
Recently all packages were build as 1.2.3-1, where "1.2.3" - was a version and "1" was a static %autorelease. But this was breaking a depedency find process. I could just replace 1 in packages.yaml, but humans are making mistakes, so full-cycle autoicrement release, while building a package.
Replaced all YAML writes with ruamel lib for simplifying code and unifying

## 2026-04-08

Surely i can say, hyprland builds are pretty stable for now (yeah-yeah-yeah, ARM builds are failing, i know). Most troubles are found, new updates are working automatically without any operator activity. Minor bugs stayed, plan to fix them later, before splitting this repo in two: for automations and repo content itself.

I think i can plan a cronjob to really check for updates nightly. I started this froject 2026-02-25 so it tooks me almost two month to reach this point.

Cool, i guess

PS. Spec file now contains versions of build requirements for better debugging
## 2026-04-05

New packages:
- Waybar - Highly customizable Wayland bar for Sway and wlroots based compositors
- cliphist - Wayland clipboard manager with support for multimedia
- uwsm - Universal Wayland Session Manager
- quickshell - Flexible QtQuick based desktop shell toolkit

.Refactored the main script, added log levels and tests, more automatic error detection. Cargo vendoring is still a mess - not tackling it yet.

## 2026-03-21

Moved the build report to its own page with more detail and COPR's native build badge. Added
build-signature caching to drastically cut rebuild counts, sped up scheduled builds with
detached COPR submissions, more errors auto-highlighted now.

## 2026-03-15

Switched from toolbox to Podman/Docker for better isolation. Merged the split YAML report into
one, made it update gradually, improved the version-update submodule, made vendoring
conditional, added `SKIP_PACKAGES`.

## 2026-03-10

I have decided not to support Fedora 42 in this repository.
Compilation of Hyprland and some of it's componens needs to increase C++ compiler version.
Also Fedora would not provide security updates for this versions after May.
I don't think it worth it to spend time on this support.
I would recommend to update to Fedora 43 in this case.

## 2026-03-01

Initial set of packages for Fedora 43.

Hyprland and its tools:

- Hyprland - Dynamic tiling Wayland compositor
- hyprland-plugins - Official plugins for Hyprland
- hyprland-protocols - Wayland protocol extensions for Hyprland
- hypridle - Idle management daemon
- hyprlock - GPU-accelerated screen lock
- hyprpaper - Blazing fast Wayland wallpaper utility
- hyprpicker - wlroots-compatible Wayland color picker
- hyprshot - Screenshot utility
- hyprsunset - Blue-light filter
- hyprsysteminfo - System info utility
- hyprlauncher - Multipurpose launcher / picker
- hyprpolkitagent - Polkit authentication agent written with hyprtoolkit
- hyprpwcenter - Volume management center
- hyprshutdown - Graceful shutdown utility
- hyprland-guiutils - Hyprland GUI utilities
- hyprqt6engine - Qt6 theme provider
- hyprland-qt-support - QML style provider for hypr* Qt apps
- xdg-desktop-portal-hyprland - XDG Desktop Portal backend for Hyprland (and wlroots)
- pyprland - Scratchpads and many goodies for Hyprland
- aylurs-gtk-shell - Scaffolding CLI for Astal+Gnim

Libraries:

- aquamarine - Very light Linux rendering backend library
- hyprcursor - Library and toolkit for the Hyprland cursor format
- hyprgraphics - Small C++ graphics utilities library
- hyprlang - Hypr configuration language library
- hyprtoolkit - Modern C++ Wayland-native GUI toolkit
- hyprutils - Small C++ utilities library
- hyprwayland-scanner - Wayland scanner replacement for Hypr projects
- hyprwire - Fast and consistent wire protocol for IPC
- gtk4-layer-shell - Library to create panels and other desktop components with GTK4 and the Layer Shell protocol
- cpptrace - Simple, portable, self-contained stacktrace library for C++11 and newer
- glaze - Extremely fast in-memory JSON and reflection library for modern C++
- glaze-v7 - Compat build of glaze 7.x for consumers pinned below 8.0
- libcava-v0 - cava 0.x built as a shared library
- libdwarf-code - Library to access DWARF debugging information
- sndio - Portable version of OpenBSD's lightweight audio and MIDI sub-system
- cliphist-git - Git snapshot build of cliphist
