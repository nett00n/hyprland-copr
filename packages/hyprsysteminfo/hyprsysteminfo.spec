
Name:           hyprsysteminfo
Version:        0.1.3
Release:        2%{?dist}
Summary:        System info utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsysteminfo
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel >= 0.7.1
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
Tag:               v0.1.3
Commit:            17f041e2d539bd63ec116a77236ea37a17c6b3e6

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprutils-devel: 0.7.1
ninja-build: 1.13.2
qt6-qtbase-devel: 6.10.3
qt6-qtbase-private-devel: 6.10.3
qt6-qtdeclarative-devel: 6.10.3
qt6-qtwayland-devel: 6.10.3

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
* Fri Jan 10 2025 nett00n <copr@nett00n.org> - 0.1.3-2

- version: bump to 0.1.3
