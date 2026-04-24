
Name:           hyprpaper
Version:        0.8.3
Release:        2%{?dist}
Summary:        A blazing fast Wayland wallpaper utility
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpaper
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  file-devel
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel >= 0.1.5
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  hyprwayland-scanner-devel >= 0.4.2
BuildRequires:  hyprwire-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libwebp)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  systemd-rpm-macros


%description
hyprpaper is a blazing fast Wayland wallpaper utility with IPC controls

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.8.3
Commit:            64b991cb917e28a51a50987a113ac4bf014ad0b7

Build dependencies:
cmake: 4.3.0
file-devel: 5.46
gcc-c++: 16.0.1
hyprgraphics-devel: 0.1.5
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
hyprwayland-scanner-devel: 0.4.2
ninja-build: 1.13.2
systemd-rpm-macros: 259.5

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_bindir}/hyprpaper
%{_userunitdir}/hyprpaper.service

%changelog
* Thu Jan 29 2026 nett00n <copr@nett00n.org> - 0.8.3-2

- version: bump to 0.8.3
