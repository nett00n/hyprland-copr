
Name:           hyprpicker
Version:        0.4.6
Release:        2%{?dist}
Summary:        A wlroots-compatible Wayland color picker that does not suck
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpicker
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Patch0:         fix-build-with-rawhide-gpp.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  hyprwayland-scanner-devel >= 0.4.2
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
Tag:               v0.4.6
Commit:            345eab2d704ee47a6c277cbfb2aeabaa620d9dbc

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
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
%{_prefix}/bin/hyprpicker
%{_prefix}/share/man/man1/hyprpicker.1.gz

%changelog
* Tue Feb 10 2026 nett00n <copr@nett00n.org> - 0.4.6-2

- version: bump to 0.4.6
