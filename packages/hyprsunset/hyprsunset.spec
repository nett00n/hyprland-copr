Name:           hyprsunset
Version:        0.3.3
Release:        %autorelease%{?dist}
Summary:        An application to enable a blue-light filter on Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsunset
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprland-protocols)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwayland-scanner)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)

%description
An application to enable a blue-light filter on Hyprland

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
%{_prefix}/bin/hyprsunset
%{_prefix}/lib/systemd/user/hyprsunset.service

%changelog
* Fri Oct 03 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.3.3-%autorelease
- tag: v0.3.3, commit: 057feb7a724b7fc0f3a406d6db08b59734db006a
- version: bump to 0.3.3
