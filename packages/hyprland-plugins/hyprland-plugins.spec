Name:           hyprland-plugins
Version:        0.53.0
Release:        %autorelease%{?dist}
Summary:        Official plugins for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-plugins
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  hyprland-devel
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xkbcommon)

%description
Official plugins for Hyprland:

- borders-plus-plus -> adds one or two additional borders to windows
- csgo-vulkan-fix -> fixes custom resolutions on CS:GO with -vulkan
- hyprbars -> adds title bars to windows
- hyprexpo -> adds an expo-like workspace overview
- hyprfocus -> flashfocus for hyprland
- hyprscrolling -> adds a scrolling layout to hyprland
- hyprtrails -> adds smooth trails behind moving windows
- hyprwinwrap -> clone of xwinwrap, allows you to put any app as a wallpaper
- xtra-dispatchers -> adds some new dispatchers

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

%changelog
* Thu Mar 05 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.53.0-%autorelease
- Update to 0.53.0
