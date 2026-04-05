%global commit b85a56b9531013c79f2f3846fd6ee2ff014b8960
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260223
Name:           hyprland-plugins
Version:        0.53.0^20260223gitb85a56b
Release:        %autorelease%{?dist}
Summary:        Official plugins for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-plugins
Source0:        %{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz
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
Commit:            b85a56b9531013c79f2f3846fd6ee2ff014b8960

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
* Mon Feb 23 2026 nett00n <copr@nett00n.org> - 0.53.0^20260223gitb85a56b-1
- all: chase hyprland
