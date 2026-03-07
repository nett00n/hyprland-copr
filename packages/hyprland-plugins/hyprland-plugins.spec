Name:           hyprland-plugins
Version:        0.53.0
Release:        %autorelease%{?dist}
Summary:        Official plugins for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-plugins
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
%doc README.md
%license LICENSE

%changelog
* Mon Dec 29 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.53.0-%autorelease
- tag: v0.53.0, commit: d7b67e8f4ba8ebeee4ce899348fcee6291512169
- v0.53.0
- -----BEGIN SSH SIGNATURE-----
- U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6r0Z7DWuB90jK6uIn817QHwUTW
- zw79TZqMStVAtQO70AAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
- AAAAQJVIuIyMXKeSIiyc31FuBqj2UZHYZkqhexbIaeKqCuswKVLDEZXjnf8qgF9Zu+n56T
- /ukNE1X5Mg3rmUM3eEpwo=
- -----END SSH SIGNATURE-----
