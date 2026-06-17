
Name:           hyprwire
Version:        0.3.1
Release:        3%{?dist}
Summary:        A fast and consistent wire protocol for IPC
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwire
Source0:        https://github.com/hyprwm/hyprwire/archive/refs/tags/v0.3.1.tar.gz#/hyprwire-0.3.1.tar.gz

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
Tag:               v0.3.1
Commit:            3e6865ce5fd9237b58f5b2ce5de18814df3baff5

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
* Sun Apr 26 2026 nett00n <copr@nett00n.org> - 0.3.1-3

- version: bump to 0.3.1
