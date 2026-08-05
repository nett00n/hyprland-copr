
Name:           hypridle
Version:        0.1.8
Release:        4%{?dist}
Summary:        An idle management daemon for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hypridle
Source0:        https://github.com/hyprwm/hypridle/archive/refs/tags/v0.1.8.tar.gz#/hypridle-0.1.8.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprland-protocols-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)



%description
Hyprland's idle daemon

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.8
Commit:            e5c01af0842bd66617f7004568df9406111d6e80

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
%{_bindir}/hypridle
%{_datadir}/hypr/hypridle.conf
%{_userunitdir}/hypridle.service

%changelog
* Sun Jul 26 2026 nett00n <copr@nett00n.org> - 0.1.8-4

- version: bump to 0.1.8
