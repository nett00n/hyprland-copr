# Hyprland Copr automation bundle for Fedora Linux

![logo](https://cdn.statically.io/gh/nett00n/hyprland-copr@main/assets/logo/hyprland-copr-x4.png)

This repo provides automations for managing COPR repo `nett00n/hyprland`.
`nett00n/hyprland` COPR repo provides packages of official and non-official but useful packages to running Hyprland on your Fedora system

[📎 Officially recommended](https://wiki.hypr.land/Getting-Started/Installation/#packages) repo solopasha/hyprland ([📎 Git](https://github.com/solopasha/hyprlandRPM/tree/master), [📎 COPR](https://copr.fedorainfracloud.org/coprs/solopasha/hyprland/)) seems to be abandoned: it has no commits in last 4+ month now

This repository is created with reproduced builds and future support convenience in mind

Feel free to reuse automation from this repository for your own copr-projects.

[📎 Check my hyprland repo on COPR](https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/)
[📎 Check my hyprland repo on GitHub](https://Github.com/nett00n/hyprland-copr/)

## Packages


### Hyprland main packages

![Hyprland](https://img.shields.io/badge/Hyprland-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)

- `hyprland` — A Modern C++ Wayland Compositor
- `hypridle` — An idle management daemon for Hyprland
- `hyprlock` — A gpu-accelerated screen lock for Hyprland
- `hyprpaper` — A blazing fast Wayland wallpaper utility
- `hyprqt6engine` — QT6 Theme Provider for Hyprland
- `xdg-desktop-portal-hyprland` — An XDG-Destop-Portal backend for Hyprland (and wlroots)
- `hyprland-plugins` — Official plugins for Hyprland
- `hyprland-qt-support` — A qml style provider for hypr* qt apps
- `hyprland-guiutils` — Hyprland GUI utilities
- `hyprlauncher` — A multipurpose and versatile launcher / picker for Hyprland
- `hyprpicker` — A wlroots-compatible Wayland color picker that does not suck
- `hyprpolkitagent` — A polkit authentication agent written in QT/QML
- `hyprpwcenter` — Volume management center for Hyprland
- `hyprshutdown` — A graceful shutdown utility for Hyprland
- `hyprsunset` — An application to enable a blue-light filter on Hyprland
- `hyprsysteminfo` — System info utility for Hyprland
- `hyprshot` — Utility to easily take screenshots in Hyprland using your mouse

### Hyprland dependencies

![Hyprland](https://img.shields.io/badge/Hyprland-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)

- `hyprwayland-scanner` — A Wayland scanner replacement for Hypr projects
- `hyprutils` — Small C++ library for utilities used across the Hypr ecosystem
- `hyprlang` — The hypr configuration language library
- `hyprgraphics` — Small C++ library for graphics utilities across the Hypr ecosystem
- `aquamarine` — A very light linux rendering backend library
- `hyprtoolkit` — A modern C++ Wayland-native GUI toolkit
- `hyprwire` — A fast and consistent wire protocol for IPC
- `hyprcursor` — A library and toolkit for the Hyprland cursor format
- `hyprland-protocols` — Wayland protocol extensions for Hyprland

### Useful apps


### Other dependencies

- `aylurs-gtk-shell` — Scaffolding CLI for Astal+Gnim
- `glaze` — Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
- `gtk4-layer-shell` — FA library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
## Build Report — Fedora 43 · 2026-03-05

> Chroot: `fedora-43-x86_64`

- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192716/) `hyprwayland-scanner`&nbsp;`0.4.5` - A Wayland scanner replacement for Hypr projects
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192718/) `hyprutils`&nbsp;`0.11.0` - Small C++ library for utilities used across the Hypr ecosystem
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192720/) `hyprlang`&nbsp;`0.6.8` - The hypr configuration language library
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192722/) `hyprgraphics`&nbsp;`0.5.0` - Small C++ library for graphics utilities across the Hypr ecosystem
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192724/) `aquamarine`&nbsp;`0.10.0` - A very light linux rendering backend library
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hyprtoolkit`&nbsp;`0.5.3` - A modern C++ Wayland-native GUI toolkit
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192737/) `hyprwire`&nbsp;`0.3.0` - A fast and consistent wire protocol for IPC
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hyprpaper`&nbsp;`0.8.3` - A blazing fast Wayland wallpaper utility
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192756/) `hyprqt6engine`&nbsp;`0.1.0` - QT6 Theme Provider for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192760/) `hyprland-protocols`&nbsp;`0.7.0` - Wayland protocol extensions for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `xdg-desktop-portal-hyprland`&nbsp;`1.3.11` - An XDG-Destop-Portal backend for Hyprland (and wlroots)
- ![other](https://img.shields.io/badge/--white?logo=gitlfs&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192764/) `glaze`&nbsp;`7.1.0` - Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hyprland`&nbsp;`0.54.1` - A Modern C++ Wayland Compositor
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hypridle`&nbsp;`0.1.7` - An idle management daemon for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hyprlock`&nbsp;`0.9.2` - A gpu-accelerated screen lock for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192806/) `hyprshot`&nbsp;`1.3.0` - Utility to easily take screenshots in Hyprland using your mouse
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192807/) `hyprcursor`&nbsp;`0.1.13` - A library and toolkit for the Hyprland cursor format
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)![copr:failed](https://img.shields.io/badge/copr-%E2%97%8B-red?style=for-the-badge) `hyprland-guiutils`&nbsp;`0.2.1` - Hyprland GUI utilities
- ![other](https://img.shields.io/badge/--white?logo=gitlfs&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192816/) `gtk4-layer-shell`&nbsp;`1.3.0` - FA library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
- ![other](https://img.shields.io/badge/--white?logo=gitlfs&logoColor=black&style=for-the-badge)![mock:success](https://img.shields.io/badge/mock-%E2%97%8F-brightgreen?style=for-the-badge)[![copr:success](https://img.shields.io/badge/copr-%E2%97%8F-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192818/) `aylurs-gtk-shell`&nbsp;`3.1.1` - Scaffolding CLI for Astal+Gnim
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprland-plugins`&nbsp;`0.53.0` - Official plugins for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprland-qt-support`&nbsp;`0.1.0` - A qml style provider for hypr* qt apps
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprlauncher`&nbsp;`0.1.5` - A multipurpose and versatile launcher / picker for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprpicker`&nbsp;`0.4.6` - A wlroots-compatible Wayland color picker that does not suck
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprpolkitagent`&nbsp;`0.1.3` - A polkit authentication agent written in QT/QML
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprpwcenter`&nbsp;`0.1.2` - Volume management center for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprshutdown`&nbsp;`0.1.0` - A graceful shutdown utility for Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprsunset`&nbsp;`0.3.3` - An application to enable a blue-light filter on Hyprland
- ![hyprland](https://img.shields.io/badge/--A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge)![mock:failed](https://img.shields.io/badge/mock-%E2%97%8B-red?style=for-the-badge)![copr:skipped](https://img.shields.io/badge/copr-%E2%97%8C-lightgrey?style=for-the-badge) `hyprsysteminfo`&nbsp;`0.1.3` - System info utility for Hyprland
---
[📎 Support me on Ko-fi ☕](https://ko-fi.com/nett00n)


# License

[GPLv3](./LICENSE.md)

**TL;DR** — You are free to use, modify, and distribute this software. If you distribute a modified version, you must release it under GPLv3 as well and make the source available. No warranty is provided.

---

# People

## Authors

- [nett00n](https://github.com/nett00n)
## Maintainers

- [nett00n](https://github.com/nett00n)

## Contributors

- Vladimir nett00n Budylnikov