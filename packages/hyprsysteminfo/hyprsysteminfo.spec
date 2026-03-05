Name:           hyprsysteminfo
Version:        0.1.3
Release:        %autorelease%{?dist}
Summary:        System info utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsysteminfo
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libpci)
BuildRequires:  pkgconfig(pixman-1)

%description
A tiny qt6/qml application to display information about the running system

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md

%changelog
* Fri Jan 10 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.3-%autorelease
- Minor stuff changes and stuff.
- qqc2-desktop-style dep is now dropped, replaced with [hyprland-qt-support](https://github.com/hyprwm/hyprland-qt-support)
- nix: move to hyprland-qt-support by @outfoxxed in https://github.com/hyprwm/hyprsysteminfo/pull/13
- **Full Changelog**: https://github.com/hyprwm/hyprsysteminfo/compare/v0.1.2...v0.1.3
