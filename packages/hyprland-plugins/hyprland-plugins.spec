%global commit b3247839c94ceb76506730841f0b3735feccf37c
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260517

Name:           hyprland-plugins
Version:        0.55.0
Release:        3%{?dist}
Summary:        Official plugins for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-plugins
Source0:        https://github.com/hyprwm/hyprland-plugins/archive/b3247839c94ceb76506730841f0b3735feccf37c/hyprland-plugins-b324783.tar.gz
Patch0:         hyprland-0.54-exclude-incompatible-plugins.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprland-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xkbcommon)


%description
hyprland-plugins

This repo houses official plugins for Hyprland.
Plugin list

- borders-plus-plus -> adds one or two additional borders to windows
- csgo-vulkan-fix -> fixes custom resolutions on CS:GO with -vulkan
- hyprbars -> adds title bars to windows
- hyprexpo -> adds an expo-like workspace overview
- hyprfocus -> flashfocus for hyprland
- hyprtrails -> adds smooth trails behind moving windows
- hyprwinwrap -> clone of xwinwrap, allows you to put any app as a wallpaper
- xtra-dispatchers -> adds some new dispatchers

Note: hyprscrolling and hyprtrails are temporarily excluded (incompatible with hyprland 0.54)

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.55.0
Commit:            90e66baf99c9025b1d5e9c9e58dd3c80d0911ea2

%prep
%autosetup -p1 -n %{name}-%{commit}

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_prefix}/lib/libborders-plus-plus.so
%{_prefix}/lib/libcsgo-vulkan-fix.so
%{_prefix}/lib/libhypr*.so
%{_prefix}/lib/libxtra-dispatchers.so

%changelog
* Wed May 13 2026 nett00n <copr@nett00n.org> - 0.55.0-3

- v0.55.0
- -----BEGIN SSH SIGNATURE-----
- U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6r0Z7DWuB90jK6uIn817QHwUTW
- zw79TZqMStVAtQO70AAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
- AAAAQEtuVyIHobR7pqUJHyjAEjzWyifwbkKyZg7nlTtxXv+lb7TgbZ1250yRS3727YmcDA
- JNbNLoy+ocEygSEDUJegc=
- -----END SSH SIGNATURE-----
