%global debug_package %{nil}

Name:           glaze
Version:        7.8.4
Release:        1%{?dist}
Summary:        Extremely fast, in memory, JSON and reflection library for modern C++.
License:        MIT
URL:            https://github.com/stephenberry/glaze.git
Source0:        https://github.com/stephenberry/glaze/archive/refs/tags/v7.8.4.tar.gz#/glaze-7.8.4.tar.gz

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
Tag:               v7.8.4
Commit:            0a21fd9dbd36963790b6f26b9539050e13d78649

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
* Thu Jul 02 2026 nett00n <copr@nett00n.org> - 7.8.4-1

- version 7.8.4 bump
