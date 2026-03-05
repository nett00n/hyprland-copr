# Hyprland Copr automation bundle for Fedora Linux

![logo](./assets/logo/hyprland-copr-x4.png)

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

| Package | Version | Mock | Copr | Description |
|:--------|:-------:|:----:|:----:|-------------|
| `hyprwayland-scanner` | ![0.4.5](https://img.shields.io/badge/0.4.5-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192716/) | A Wayland scanner replacement for Hypr projects |
| `hyprutils` | ![0.11.0](https://img.shields.io/badge/0.11.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192718/) | Small C++ library for utilities used across the Hypr ecosystem |
| `hyprlang` | ![0.6.8](https://img.shields.io/badge/0.6.8-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192720/) | The hypr configuration language library |
| `hyprgraphics` | ![0.5.0](https://img.shields.io/badge/0.5.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192722/) | Small C++ library for graphics utilities across the Hypr ecosystem |
| `aquamarine` | ![0.10.0](https://img.shields.io/badge/0.10.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192724/) | A very light linux rendering backend library |
| `hyprtoolkit` | ![0.5.3](https://img.shields.io/badge/0.5.3-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | A modern C++ Wayland-native GUI toolkit |
| `hyprwire` | ![0.3.0](https://img.shields.io/badge/0.3.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192737/) | A fast and consistent wire protocol for IPC |
| `hyprpaper` | ![0.8.3](https://img.shields.io/badge/0.8.3-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | A blazing fast Wayland wallpaper utility |
| `hyprqt6engine` | ![0.1.0](https://img.shields.io/badge/0.1.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192756/) | QT6 Theme Provider for Hyprland |
| `hyprland-protocols` | ![0.7.0](https://img.shields.io/badge/0.7.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192760/) | Wayland protocol extensions for Hyprland |
| `xdg-desktop-portal-hyprland` | ![1.3.11](https://img.shields.io/badge/1.3.11-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | An XDG-Destop-Portal backend for Hyprland (and wlroots) |
| `glaze` | ![7.1.0](https://img.shields.io/badge/7.1.0-D6D6D6?logo=gitlfs&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192764/) | Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF |
| `hyprland` | ![0.54.1](https://img.shields.io/badge/0.54.1-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | A Modern C++ Wayland Compositor |
| `hypridle` | ![0.1.7](https://img.shields.io/badge/0.1.7-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | An idle management daemon for Hyprland |
| `hyprlock` | ![0.9.2](https://img.shields.io/badge/0.9.2-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | A gpu-accelerated screen lock for Hyprland |
| `hyprshot` | ![1.3.0](https://img.shields.io/badge/1.3.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192806/) | Utility to easily take screenshots in Hyprland using your mouse |
| `hyprcursor` | ![0.1.13](https://img.shields.io/badge/0.1.13-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192807/) | A library and toolkit for the Hyprland cursor format |
| `hyprland-guiutils` | ![0.2.1](https://img.shields.io/badge/0.2.1-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-failed-red?style=for-the-badge) | Hyprland GUI utilities |
| `gtk4-layer-shell` | ![1.3.0](https://img.shields.io/badge/1.3.0-D6D6D6?logo=gitlfs&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192816/) | FA library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4 |
| `aylurs-gtk-shell` | ![3.1.1](https://img.shields.io/badge/3.1.1-D6D6D6?logo=gitlfs&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-success-brightgreen?style=for-the-badge) | [![copr](https://img.shields.io/badge/copr-success-brightgreen?style=for-the-badge)](https://copr.fedorainfracloud.org/coprs/build/10192818/) | Scaffolding CLI for Astal+Gnim |
| `hyprland-plugins` | ![0.53.0](https://img.shields.io/badge/0.53.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | Official plugins for Hyprland |
| `hyprland-qt-support` | ![0.1.0](https://img.shields.io/badge/0.1.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | A qml style provider for hypr* qt apps |
| `hyprlauncher` | ![0.1.5](https://img.shields.io/badge/0.1.5-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | A multipurpose and versatile launcher / picker for Hyprland |
| `hyprpicker` | ![0.4.6](https://img.shields.io/badge/0.4.6-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | A wlroots-compatible Wayland color picker that does not suck |
| `hyprpolkitagent` | ![0.1.3](https://img.shields.io/badge/0.1.3-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | A polkit authentication agent written in QT/QML |
| `hyprpwcenter` | ![0.1.2](https://img.shields.io/badge/0.1.2-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | Volume management center for Hyprland |
| `hyprshutdown` | ![0.1.0](https://img.shields.io/badge/0.1.0-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | A graceful shutdown utility for Hyprland |
| `hyprsunset` | ![0.3.3](https://img.shields.io/badge/0.3.3-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | An application to enable a blue-light filter on Hyprland |
| `hyprsysteminfo` | ![0.1.3](https://img.shields.io/badge/0.1.3-A5F3FC?logo=hyprland&logoColor=black&style=for-the-badge) | ![mock](https://img.shields.io/badge/mock-failed-red?style=for-the-badge) | ![copr](https://img.shields.io/badge/copr-skipped-lightgrey?style=for-the-badge) | System info utility for Hyprland |
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