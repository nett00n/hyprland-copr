
Name:           hyprsunset
Version:        0.3.3
Release:        2%{?dist}
Summary:        An application to enable a blue-light filter on Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsunset
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprland-protocols-devel >= 0.4.0
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  hyprwayland-scanner-devel >= 0.4.2
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)


%description
An application to enable a blue-light filter on Hyprland

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.3.3
Commit:            057feb7a724b7fc0f3a406d6db08b59734db006a

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprland-protocols-devel: 0.4.0
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
hyprwayland-scanner-devel: 0.4.2
ninja-build: 1.13.2

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
* Fri Oct 03 2025 nett00n <copr@nett00n.org> - 0.3.3-2

- version: bump to 0.3.3
