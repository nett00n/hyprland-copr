
Name:           hyprwayland-scanner
Version:        0.4.5
Release:        2%{?dist}
Summary:        A Wayland scanner replacement for Hypr projects
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwayland-scanner
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(pugixml)


%description
hyprwayland-scanner is a Wayland protocol scanner / code generatorused
by the Hypr ecosystem to generate C++ protocol bindings

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.4.5
Commit:            fcca0c61f988a9d092cbb33e906775014c61579d

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
ninja-build: 1.13.2

%prep
%autosetup -p1

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
* Mon Jul 07 2025 nett00n <copr@nett00n.org> - 0.4.5-2

- version: bump to 0.4.5
