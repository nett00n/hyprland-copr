Name:           xdg-desktop-portal-hyprland
Version:        1.3.11
Release:        %autorelease%{?dist}
Summary:        An XDG-Destop-Portal backend for Hyprland (and wlroots)

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/xdg-desktop-portal-hyprland
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(hyprland-protocols)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwayland-scanner)
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

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md
%{_bindir}/hyprland-share-picker
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.hyprland.service
%{_datadir}/xdg-desktop-portal/portals/hyprland.portal
%{_libexecdir}/%{name}
%{_userunitdir}/%{name}.service

%changelog
* Fri Oct 17 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 1.3.11-%autorelease
- Minor update with a few fixes
- portals: Fix use of a potentially destroyed session by @PlasmaPower in https://github.com/hyprwm/xdg-desktop-portal-hyprland/pull/355
- screencopy: fix callback resetting by @vaxerski in https://github.com/hyprwm/xdg-desktop-portal-hyprland/pull/358
- @PlasmaPower made their first contribution in https://github.com/hyprwm/xdg-desktop-portal-hyprland/pull/355
- **Full Changelog**: https://github.com/hyprwm/xdg-desktop-portal-hyprland/compare/v1.3.10...v1.3.11
