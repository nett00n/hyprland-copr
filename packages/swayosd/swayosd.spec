
Name:           swayosd
Version:        0.3.2
Release:        5%{?dist}
Summary:        A GTK based on screen display for keyboard shortcuts like caps-lock and volume
License:        GPL-3.0-or-later
URL:            https://github.com/ErikReider/SwayOSD
Source0:        https://github.com/ErikReider/SwayOSD/archive/refs/tags/v0.3.2.tar.gz#/swayosd-0.3.2.tar.gz
Source1:        swayosd-0.3.2-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  dbus-devel
BuildRequires:  gcc
BuildRequires:  glib2-devel
BuildRequires:  gtk4-devel
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libevdev)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(libpulse)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  rustc
BuildRequires:  sassc
BuildRequires:  systemd-devel



%description
A GTK based on-screen display (OSD) for keyboard shortcuts like caps-lock and volume.

Shows a themeable OSD popup for volume, brightness, capslock/numlock/scrolllock, and
other hardware key events on Wayland compositors such as Hyprland and Sway.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.3.2
Commit:            42f4a3190f0449042db00d1cbb39b8b626d63c7b

%prep
%autosetup -p1 -n SwayOSD-%{version}
tar xf %{SOURCE1}

%build
%global _libdir %{_prefix}/lib
%meson --buildtype=release
%meson_build

%install
%meson_install

%files
%config(noreplace) %{_sysconfdir}/xdg/swayosd/backend.toml
%config(noreplace) %{_sysconfdir}/xdg/swayosd/config.toml
%doc README.md
%license LICENSE
%{_bindir}/swayosd-client
%{_bindir}/swayosd-libinput-backend
%{_bindir}/swayosd-server
%{_datadir}/dbus-1/system-services/org.erikreider.swayosd.service
%{_datadir}/dbus-1/system.d/org.erikreider.swayosd.conf
%{_datadir}/polkit-1/actions/org.erikreider.swayosd.policy
%{_datadir}/polkit-1/rules.d/org.erikreider.swayosd.rules
%{_prefix}/lib/udev/rules.d/99-swayosd.rules
%{_sysconfdir}/xdg/swayosd/style.css
%{_unitdir}/swayosd-libinput-backend.service

%package devel
Summary:        Development files for A GTK based on screen display for keyboard shortcuts like caps-lock and volume
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for swayosd.

%files devel

%changelog
* Mon Jun 22 2026 nett00n <copr@nett00n.org> - 0.3.2-5

- Arvid Eriksson (1):
- Fix --top-margin positioning with fractional scaling (#242)
- Erik Reider (10):
- Fixed Cargo.lock version not being up-to-date
- Fixed OSD window not sharing the same custom duration
- Simplified de-duplicated action activation logic for similar actions
- Retry a connection to Pulse if failed for each audio action
- Vastly simplified action and option transfer between swayosd client and server
- Fixed duration in config not causing a panic
- Fixed formatting
- Added volume mute and unmute. Fixes #76
- Simplified development by removing the need of the meson devenv
- Bumped version to 0.3.2
- Peter Löffler (1):
- feat: add duration argument to swayosd-server (#207)
- William Wernert (1):
- Replace pulsectl-rs with local pulse module (#241)
- holly (1):
- 'loweres' -> 'lowers' (#235)
- roib (1):
- Fix integer division in kbd backlight progress bar calculation (#237)
