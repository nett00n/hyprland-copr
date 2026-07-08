
Name:           hyprsysteminfo
Version:        0.2.0
Release:        8%{?dist}
Summary:        System info utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsysteminfo
Source0:        https://github.com/hyprwm/hyprsysteminfo/archive/refs/tags/v0.2.0.tar.gz#/hyprsysteminfo-0.2.0.tar.gz

BuildRequires:  aquamarine
BuildRequires:  aquamarine-devel
BuildRequires:  cairo-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glaze
BuildRequires:  glaze-devel
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libpci)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtquickcontrols2-devel
BuildRequires:  qt6-qtwayland-devel



%description
A tiny qt6/qml application to display information about the running system

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.2.0
Commit:            6f68a726531b53d87c6dd6ce474face27dde02ff

%prep
%autosetup -p1
sed -i '/find_package(Qt6.*WaylandClient)/a find_package(Qt6 REQUIRED COMPONENTS WaylandClientPrivate)' CMakeLists.txt

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_prefix}/bin/hyprsysteminfo
%{_prefix}/share/applications/hyprsysteminfo.desktop

%changelog
* Sun Apr 26 2026 nett00n <copr@nett00n.org> - 0.2.0-8

- version: bump to 0.2.0
