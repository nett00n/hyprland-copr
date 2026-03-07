Name:           hyprtoolkit
Version:        0.5.3
Release:        %autorelease%{?dist}
Summary:        A modern C++ Wayland-native GUI toolkit
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprtoolkit
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(aquamarine)
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(hyprgraphics)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(iniparser)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)

%description
A modern C++ Wayland-native GUI toolkit

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprtoolkit.so*

%package devel
Summary:        Development files for A modern C++ Wayland-native GUI toolkit
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprtoolkit.

%files devel
%{_includedir}/hyprtoolkit/
%{_libdir}/pkgconfig/hyprtoolkit.pc

%changelog
* Thu Jan 22 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.5.3-%autorelease
- tag: v0.5.3, commit: 71515e83eb7ad0ec921c913e1d5772e5fe55daa9
- version: bump to 0.5.3
