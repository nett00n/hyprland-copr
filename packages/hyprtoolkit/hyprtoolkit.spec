Name:           hyprtoolkit
Version:        0.5.3
Release:        %autorelease%{?dist}
Summary:        A modern C++ Wayland-native GUI toolkit
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprtoolkit
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Patch0:         fix-build-with-rawhide-gpp.patch

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(iniparser)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)

%description
A modern C++ Wayland-native GUI toolkit

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:
Tag:               v0.5.3
Commit:            71515e83eb7ad0ec921c913e1d5772e5fe55daa9

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprtoolkit.so*

%package devel
Summary:        Development files for A modern C++ Wayland-native GUI toolkit
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprtoolkit.

%files devel
%{_includedir}/hyprtoolkit/
%{_libdir}/pkgconfig/hyprtoolkit.pc

%changelog
* Thu Jan 22 2026 nett00n <copr@nett00n.org> - 0.5.3-%autorelease
- version: bump to 0.5.3
