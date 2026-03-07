Name:           hyprutils
Version:        0.11.0
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
hyprutils is a small C++ library used across the Hypr* ecosystem for
various utilities such as memory management, signals, and more

%prep
%autosetup

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
* Fri Dec 05 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.11.0-%autorelease
- tag: v0.11.0, commit: fe686486ac867a1a24f99c753bb40ffed338e4b0
- version: bump to 0.11.0
