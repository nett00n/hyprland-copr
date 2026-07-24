%global commit b3247839c94ceb76506730841f0b3735feccf37c
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260517

Name:           hyprland-plugins
Version:        0.56.0
Release:        1%{?dist}
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
Tag:               v0.56.0
Commit:            7644cecdb947060682891a0db2a0cdc5c0b9e704

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
%{_prefix}/lib/libhypr*.so

%changelog
* Mon Jul 20 2026 nett00n <copr@nett00n.org> - 0.56.0-1

- v0.56.0
- -----BEGIN SSH SIGNATURE-----
- U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg4vfCZPfelzgrVHHxdluu2XrLU6
- Fl5wIcXPvtAXjG9oAAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
- AAAAQJY+a+a/VCzsH/q34Wwy5Mp5XfXZvwULzX52GLq4lFSehqymrnGeCibAga4gJ0Spsm
- DIyNKZVwN1WCtWp6KPUQU=
- -----END SSH SIGNATURE-----
