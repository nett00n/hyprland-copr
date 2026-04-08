Name:           xdg-desktop-portal-hyprland
Version:        1.3.11
Release:        %autorelease%{?dist}
Summary:        An XDG-Destop-Portal backend for Hyprland (and wlroots)
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/xdg-desktop-portal-hyprland
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
Tag:               v1.3.11
Commit:            753bbbdf6a052994da94062e5b753288cef28dfb

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprland-protocols-devel: 0.4.0
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
hyprwayland-scanner-devel: 0.4.2
ninja-build: 1.13.2
qt6-qtbase-devel: 6.10.3
qt6-qtwayland-devel: 6.10.3
sdbus-cpp: 2.2.1
systemd-rpm-macros: 259.5

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
* Fri Oct 17 2025 nett00n <copr@nett00n.org> - 1.3.11-1
- version: bump to 1.3.11
