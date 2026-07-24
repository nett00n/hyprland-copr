
Name:           xdg-desktop-portal-hyprland
Version:        1.4.0
Release:        1%{?dist}
Summary:        An XDG-Destop-Portal backend for Hyprland (and wlroots)
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/xdg-desktop-portal-hyprland
Source0:        https://github.com/hyprwm/xdg-desktop-portal-hyprland/archive/refs/tags/v1.4.0.tar.gz#/xdg-desktop-portal-hyprland-1.4.0.tar.gz

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
Tag:               v1.4.0
Commit:            f36f5ff9e94dc5698d6a66e5cebd8d6b2e599068

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
* Sat Jul 18 2026 nett00n <copr@nett00n.org> - 1.4.0-1

- version: bump to 1.4.0
