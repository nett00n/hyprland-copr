%global commit 00862ca3e2908857f9660adbba1b2d55796aaa43
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260805

Name:           hyprland-plugins
Version:        0.56.0^20260805git00862ca
Release:        3%{?dist}
Summary:        Official plugins for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-plugins
Source0:        https://github.com/hyprwm/hyprland-plugins/archive/00862ca3e2908857f9660adbba1b2d55796aaa43/hyprland-plugins-00862ca.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glslang-devel
BuildRequires:  hyprland-devel
BuildRequires:  lua-devel
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
Commit:            00862ca3e2908857f9660adbba1b2d55796aaa43

%prep
%autosetup -p1 -n %{name}-%{commit}
# hyprfocus: chase hyprland desktop/view refactor (m_isFloating is a
# plain member on the CWindow shipped by our packaged Hyprland version;
# the isFloating() accessor lands in a later Hyprland release)
sed -i \
  -e 's|window->isFloating()|window->m_isFloating|' \
  -e 's|w->isFloating()|w->m_isFloating|g' \
  hyprfocus/main.cpp


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
%{_prefix}/lib/libhyprbars.so
%{_prefix}/lib/libhyprfocus.so

%changelog
* Wed Aug 05 2026 nett00n <copr@nett00n.org> - 0.56.0^20260805git00862ca-3

- hyprpm: add pin for 0.56.2
