
Name:           cpptrace
Version:        1.0.4
Release:        14%{?dist}
Summary:        Simple, portable, and self-contained stacktrace library for C++11 and newer
License:        MIT
URL:            https://github.com/jeremy-rifkin/cpptrace.git
Source0:        https://github.com/jeremy-rifkin/cpptrace/archive/refs/tags/v%{version}.tar.gz#/cpptrace-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  libdwarf-devel
BuildRequires:  libzstd
BuildRequires:  libzstd-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libdwarf)
BuildRequires:  pkgconfig(libunwind)


%description
Simple, portable, and self-contained C++ stacktrace library

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.0.4
Commit:            3db8da80111171c219ab5839905771386bee06b3

%prep
%autosetup -p1

%build
%cmake -DCPPTRACE_USE_EXTERNAL_ZSTD=ON -DCPPTRACE_USE_EXTERNAL_LIBDWARF=ON -DCPPTRACE_FIND_LIBDWARF_WITH_PKGCONFIG=ON -DCPPTRACE_UNWIND_WITH_LIBUNWIND=ON
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_libdir}/libcpptrace.so*

%package devel
Summary:        Development files for Simple, portable, and self-contained stacktrace library for C++11 and newer
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for cpptrace.

%files devel
%{_includedir}/cpptrace/*.hpp
%{_includedir}/ctrace/ctrace.h
%{_libdir}/cmake/cpptrace/cpptrace-*.cmake
%{_libdir}/cmake/cpptrace/Findzstd.cmake

%changelog
* Thu Jul 24 2025 nett00n <copr@nett00n.org> - 1.0.4-14

- Bump to v1.0.4
