%global debug_package %{nil}

Name:           glaze-v7
Version:        7.9.1
Release:        8%{?dist}
Summary:        Compat build of glaze 7.x for consumers pinned below 8.0
License:        MIT
URL:            https://github.com/stephenberry/glaze
Source0:        https://github.com/stephenberry/glaze/archive/refs/tags/v7.9.1.tar.gz#/glaze-v7-7.9.1.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  libasan
BuildRequires:  libubsan
BuildRequires:  ninja-build



%description
One of the fastest JSON libraries in the world. Glaze reads and
writes from object memory, simplifying interfaces and offering incredible
performance

Compat build of glaze 7.x, installed to versioned paths alongside the
main glaze package, for consumers that pin below glaze 8.0 (e.g.
Hyprland's find_package(glaze 7...<8)).

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n glaze-%{version}

%build
%cmake -DBUILD_TESTING=OFF -DCMAKE_INSTALL_INCLUDEDIR=include/glaze-v7 -Dglaze_INSTALL_CMAKEDIR=%{_datadir}/glaze-v7
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE

%package devel
Summary:        Development files for Compat build of glaze 7.x for consumers pinned below 8.0
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for glaze-v7.

%files devel
%{_datadir}/glaze-v7/*.cmake
%{_includedir}/glaze-v7/

%changelog
* Sat Aug 08 2026 nett00n <copr@nett00n.org> - 7.9.1-8

- Update to 7.9.1
