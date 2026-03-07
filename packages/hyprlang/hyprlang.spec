Name:           hyprlang
Version:        0.6.8
Release:        %autorelease%{?dist}
Summary:        The hypr configuration language library
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlang
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprutils)

%description
hyprlang is the official implementation library for the hypr configuration language

%prep
%autosetup

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
* Mon Jan 05 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.6.8-%autorelease
- tag: v0.6.8, commit: 3a1c1b25b059dae2c6bbc46991562ba1158d125c
- version: bump to 0.6.8
