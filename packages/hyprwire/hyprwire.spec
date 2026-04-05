Name:           hyprwire
Version:        0.3.0
Release:        %autorelease%{?dist}
Summary:        A fast and consistent wire protocol for IPC
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwire
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libffi)
BuildRequires:  pkgconfig(pugixml)

%description
A fast and consistent wire protocol for IPC

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:
Tag:               v0.3.0
Commit:            37bc90eed02b0c8b5a77a0b00867baf3005cfb98

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_bindir}/hyprwire-scanner
%{_libdir}/libhyprwire.so*

%package devel
Summary:        Development files for A fast and consistent wire protocol for IPC
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprwire.

%files devel
%{_includedir}/hyprwire/
%{_libdir}/cmake/hyprwire-scanner/
%{_libdir}/pkgconfig/hyprwire-scanner.pc
%{_libdir}/pkgconfig/hyprwire.pc

%changelog
* Wed Feb 04 2026 nett00n <copr@nett00n.org> - 0.3.0-1
- version: bump to 0.3.0
