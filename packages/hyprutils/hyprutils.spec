
Name:           hyprutils
Version:        0.14.3
Release:        1%{?dist}
Summary:        Small C++ library for utilities used across the Hypr ecosystem
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprutils
Source0:        https://github.com/hyprwm/hyprutils/archive/refs/tags/v0.14.3.tar.gz#/hyprutils-0.14.3.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(pixman-1)




%description
hyprutils is a small C++ library used across the Hypr* ecosystem
forvarious utilities such as memory management, signals, and more

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.14.3
Commit:            0d13d5a624eb093b600d1b2cbe448fb613c86424

%prep
%autosetup -p1

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
* Thu Oct 22 2026 nett00n <copr@nett00n.org> - 0.14.3-1

- VERSION: bump to 0.14.3
