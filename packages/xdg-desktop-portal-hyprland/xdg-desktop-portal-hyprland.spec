
Name:           xdg-desktop-portal-hyprland
Version:        1.3.12
Release:        2%{?dist}
Summary:        An XDG-Destop-Portal backend for Hyprland (and wlroots)
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/xdg-desktop-portal-hyprland
Source0:        https://github.com/hyprwm/xdg-desktop-portal-hyprland/archive/refs/tags/v1.3.12.tar.gz#/xdg-desktop-portal-hyprland-1.3.12.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprland-protocols-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(libspa-0.2)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(Qt6Widgets)
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wayland-scanner)
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtwayland-devel
BuildRequires:  sdbus-cpp
BuildRequires:  systemd-rpm-macros


%description
xdg-desktop-portal backend for Hyprland

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.3.12
Commit:            01e13c0a027a2d177df4dead76ac9d069e2cc8e6

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprland-share-picker
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.hyprland.service
%{_datadir}/xdg-desktop-portal/portals/hyprland.portal
%{_libexecdir}/%{name}
%{_userunitdir}/%{name}.service

%changelog
* Sun Apr 26 2026 nett00n <copr@nett00n.org> - 1.3.12-2

- version: bump to 1.3.12
