Name:           hyprpicker
Version:        0.4.6
Release:        %autorelease%{?dist}
Summary:        A wlroots-compatible Wayland color picker that does not suck
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpicker
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwayland-scanner)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)

%description
A wlroots-compatible Wayland color picker that does not suck

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
%{_prefix}/bin/hyprpicker
%{_prefix}/share/man/man1/hyprpicker.1.gz

%changelog
* Tue Feb 10 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.4.6-%autorelease
- tag: v0.4.6, commit: 345eab2d704ee47a6c277cbfb2aeabaa620d9dbc
- version: bump to 0.4.6
