Name:           hyprwire
Version:        0.3.0
Release:        %autorelease%{?dist}
Summary:        A fast and consistent wire protocol for IPC
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwire
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libffi)
BuildRequires:  pkgconfig(pugixml)

%description
A fast and consistent wire protocol for IPC

%prep
%autosetup

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
* Wed Feb 04 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.3.0-%autorelease
- tag: v0.3.0, commit: 37bc90eed02b0c8b5a77a0b00867baf3005cfb98
- version: bump to 0.3.0
