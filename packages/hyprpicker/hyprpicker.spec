%global upstream_commit_subject VERSION: bump to 0.4.8
%global upstream_commits 145

Name:           hyprpicker
Version:        0.4.8
Release:        3%{?dist}
Summary:        A wlroots-compatible Wayland color picker that does not suck
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpicker
Source0:        https://github.com/hyprwm/hyprpicker/archive/refs/tags/v0.4.8.tar.gz#/hyprpicker-0.4.8.tar.gz

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
Tag:               v0.4.8
Commit:            838147963f8c2a22b60a455b2ccc02b5aa4a7b98

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
%{_bindir}/hyprpicker
%{_mandir}/man1/hyprpicker.1.gz

%changelog
* Sun Nov 01 2026 nett00n <copr@nett00n.org> - 0.4.8-3

- VERSION: bump to 0.4.8
