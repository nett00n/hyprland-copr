Name:           hyprwayland-scanner
Version:        0.4.5
Release:        %autorelease%{?dist}
Summary:        A Wayland scanner replacement for Hypr projects
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwayland-scanner
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(pugixml)

%description
hyprwayland-scanner is a Wayland protocol scanner / code generator
used by the Hypr ecosystem to generate C++ protocol bindings

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_bindir}/hyprwayland-scanner

%package devel
Summary:        Development files for A Wayland scanner replacement for Hypr projects
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprwayland-scanner.

%files devel
%{_libdir}/cmake/hyprwayland-scanner/
%{_libdir}/pkgconfig/hyprwayland-scanner.pc

%changelog
* Mon Jul 07 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.4.5-%autorelease
- tag: v0.4.5, commit: fcca0c61f988a9d092cbb33e906775014c61579d
- version: bump to 0.4.5
