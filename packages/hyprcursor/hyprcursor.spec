Name:           hyprcursor
Version:        0.1.13
Release:        %autorelease%{?dist}
Summary:        A library and toolkit for the Hyprland cursor format
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprcursor
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(librsvg-2.0)
BuildRequires:  pkgconfig(libzip)
BuildRequires:  pkgconfig(tomlplusplus)

%description
The hyprland cursor format, library and utilities

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
%{_bindir}/hyprcursor-util
%{_libdir}/libhyprcursor.so*

%package devel
Summary:        Development files for A library and toolkit for the Hyprland cursor format
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprcursor.

%files devel
%{_includedir}/hyprcursor.hpp
%{_includedir}/hyprcursor/
%{_libdir}/pkgconfig/hyprcursor.pc

%changelog
* Thu Jul 31 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.13-%autorelease
- tag: v0.1.13, commit: 44e91d467bdad8dcf8bbd2ac7cf49972540980a5
- version: bump to 0.1.13
