Name:           hyprlang
Version:        0.6.8
Release:        %autorelease%{?dist}
Summary:        The hypr configuration language library
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlang
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build

%description
hyprlang is the official implementation library for the hypr configuration
language

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.6.8
Commit:            3a1c1b25b059dae2c6bbc46991562ba1158d125c

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprutils-devel: 0.7.1
ninja-build: 1.13.2

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprlang.so*

%package devel
Summary:        Development files for The hypr configuration language library
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprlang.

%files devel
%{_includedir}/hyprlang.hpp
%{_libdir}/pkgconfig/hyprlang.pc

%changelog
* Mon Jan 05 2026 nett00n <copr@nett00n.org> - 0.6.8-1
- version: bump to 0.6.8
