
Name:           hyprcursor
Version:        0.1.14
Release:        1%{?dist}
Summary:        A library and toolkit for the Hyprland cursor format
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprcursor
Source0:        https://github.com/hyprwm/hyprcursor/archive/refs/tags/v0.1.14.tar.gz#/hyprcursor-0.1.14.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprlang-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(librsvg-2.0)
BuildRequires:  pkgconfig(libzip)
BuildRequires:  pkgconfig(tomlplusplus)




%description
The hyprland cursor format, library and utilities

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.14
Commit:            9e6916077f3c6c20419e8e405c51952fc37aaa5b

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
* Mon Nov 09 2026 nett00n <copr@nett00n.org> - 0.1.14-1

- VERSION: bump to 0.1.14
