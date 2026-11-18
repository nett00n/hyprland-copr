%global upstream_commit_subject VERSION: bump to 0.14.4
%global upstream_commits 217

Name:           hyprutils
Version:        0.14.4
Release:        1%{?dist}
Summary:        Small C++ library for utilities used across the Hypr ecosystem
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprutils
Source0:        https://github.com/hyprwm/hyprutils/archive/refs/tags/v0.14.4.tar.gz#/hyprutils-0.14.4.tar.gz

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
Tag:               v0.14.4
Commit:            73d41c6ad7ca5a13b059ac31980731afbfc825a3

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
* Tue Nov 17 2026 nett00n <copr@nett00n.org> - 0.14.4-1

- VERSION: bump to 0.14.4
