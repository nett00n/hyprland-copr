
Name:           hyprsunset
Version:        0.4.0
Release:        1%{?dist}
Summary:        An application to enable a blue-light filter on Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsunset
Source0:        https://github.com/hyprwm/hyprsunset/archive/refs/tags/v0.4.0.tar.gz#/hyprsunset-0.4.0.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprland-protocols-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)



%description
An application to enable a blue-light filter on Hyprland

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.4.0
Commit:            25f704346ec22e7623b0873ef8c4573b57ca1512

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
%{_prefix}/bin/hyprsunset
%{_prefix}/lib/systemd/user/hyprsunset.service

%changelog
* Mon Jul 13 2026 nett00n <copr@nett00n.org> - 0.4.0-1

- version: bump to 0.4.0
