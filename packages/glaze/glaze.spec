%global debug_package %{nil}
Name:           glaze
Version:        7.1.0
Release:        %autorelease%{?dist}
Summary:        Extremely fast, in memory, JSON and reflection library for modern C++.
License:        MIT
URL:            https://github.com/stephenberry/glaze
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  libasan
BuildRequires:  libubsan
BuildRequires:  ninja-build

%description
One of the fastest JSON libraries in the world. Glaze reads and
writes from object memory, simplifying interfaces and offering incredible
performance

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:
Tag:               v7.1.0
Commit:            b71542bb16c9d793545062185d7fd9bedbc0b638

%prep
%autosetup -p1

%build
%cmake -DBUILD_TESTING=OFF
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE

%package devel
Summary:        Development files for Extremely fast, in memory, JSON and reflection library for modern C++.
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for glaze.

%files devel
%{_prefix}/include/glaze/
%{_prefix}/share/glaze/*.cmake

%changelog
* Sat Feb 28 2026 nett00n <copr@nett00n.org> - 7.1.0-1
- v7.1.0 bump
