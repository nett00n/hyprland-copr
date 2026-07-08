
Name:           hyprpaper
Version:        0.8.4
Release:        6%{?dist}
Summary:        A blazing fast Wayland wallpaper utility
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpaper
Source0:        https://github.com/hyprwm/hyprpaper/archive/refs/tags/v0.8.4.tar.gz#/hyprpaper-0.8.4.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  file-devel
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
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
Tag:               v0.8.4
Commit:            20fc0fa6c2056c388a4cd69cb394a9f989dd27c0

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
* Wed Apr 29 2026 nett00n <copr@nett00n.org> - 0.8.4-6

- version: bump to 0.8.4
