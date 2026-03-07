Name:           hypridle
Version:        0.1.7
Release:        %autorelease%{?dist}
Summary:        An idle management daemon for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hypridle
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprland-protocols)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)

%description
Hyprland's idle daemon

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
%{_bindir}/hypridle
%{_datadir}/hypr/hypridle.conf
%{_userunitdir}/hypridle.service

%changelog
* Wed Aug 27 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.7-%autorelease
- tag: v0.1.7, commit: 5430b73ddf148651bcf35fa39ed4d757c7534028
- version: bump to 0.1.7
