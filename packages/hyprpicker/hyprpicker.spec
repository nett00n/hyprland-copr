
Name:           hyprpicker
Version:        0.4.7
Release:        5%{?dist}
Summary:        A wlroots-compatible Wayland color picker that does not suck
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpicker
Source0:        https://github.com/hyprwm/hyprpicker/archive/refs/tags/v0.4.7.tar.gz#/hyprpicker-0.4.7.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)



%description
A wlroots-compatible Wayland color picker that does not suck

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.4.7
Commit:            8c163ce9b8a40f85babe4dd6e23a238787351164

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
%{_prefix}/bin/hyprpicker
%{_prefix}/share/man/man1/hyprpicker.1.gz

%changelog
* Tue May 05 2026 nett00n <copr@nett00n.org> - 0.4.7-5

- version: bump to 0.4.7
