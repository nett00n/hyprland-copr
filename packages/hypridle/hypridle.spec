Name:           hypridle
Version:        0.1.7
Release:        %autorelease%{?dist}
Summary:        An idle management daemon for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hypridle
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
Tag:               v0.1.7
Commit:            5430b73ddf148651bcf35fa39ed4d757c7534028

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
* Wed Aug 27 2025 nett00n <copr@nett00n.org> - 0.1.7-1
- version: bump to 0.1.7
