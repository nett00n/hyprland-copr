Name:           hyprutils
Version:        0.12.0
Release:        %autorelease%{?dist}
Summary:        Small C++ library for utilities used across the Hypr ecosystem
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprutils
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(pixman-1)

%description
hyprutils is a small C++ library used across the Hypr* ecosystem
forvarious utilities such as memory management, signals, and more

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:
Tag:               v0.12.0
Commit:            e6caa3d4d1427eedbdf556cf4ceb70f2d9c0b56d

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprutils.so*

%package devel
Summary:        Development files for Small C++ library for utilities used across the Hypr ecosystem
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprutils.

%files devel
%{_includedir}/hyprutils/
%{_libdir}/pkgconfig/hyprutils.pc

%changelog
* Mon Mar 30 2026 nett00n <copr@nett00n.org> - 0.12.0-1
- version: bump to 0.12.0
