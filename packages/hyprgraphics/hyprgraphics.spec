Name:           hyprgraphics
Version:        0.5.0
Release:        %autorelease%{?dist}
Summary:        Small C++ library for graphics utilities across the Hypr ecosystem
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprgraphics
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  file-devel
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  librsvg2-devel
BuildRequires:  ninja-build
BuildRequires:  pango-devel
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libwebp)
BuildRequires:  pkgconfig(pixman-1)

%description
hyprgraphics is a small C++ library used across the Hypr* ecosystem for
graphics-related utilities such as image loading and color management

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:
Tag:               v0.5.0
Commit:            4af02a3925b454deb1c36603843da528b67ded6c

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprgraphics.so*

%package devel
Summary:        Development files for Small C++ library for graphics utilities across the Hypr ecosystem
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprgraphics.

%files devel
%{_includedir}/hyprgraphics/
%{_libdir}/pkgconfig/hyprgraphics.pc

%changelog
* Sun Dec 28 2025 nett00n <copr@nett00n.org> - 0.5.0-1
- version: bump to 0.5.0
