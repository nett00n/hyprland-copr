Name:           hyprsysteminfo
Version:        0.1.3
Release:        %autorelease%{?dist}
Summary:        System info utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsysteminfo
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(hyprutils)
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

%prep
%autosetup
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
* Fri Jan 10 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.3-%autorelease
- tag: v0.1.3, commit: 17f041e2d539bd63ec116a77236ea37a17c6b3e6
- version: bump to 0.1.3
