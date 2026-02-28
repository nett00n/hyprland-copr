Name:           hyprlang
Version:        0.6.8
Release:        %autorelease%{?dist}
Summary:        The hypr configuration language library

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlang
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprutils)

%description
hyprlang is the official implementation library for the hypr configuration language.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprlang.so.*

%package devel
Summary:        Development files for The hypr configuration language library
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprlang.

%files devel
%{_includedir}/hyprlang.hpp
%{_libdir}/libhyprlang.so
%{_libdir}/pkgconfig/hyprlang.pc

%changelog
* Mon Jan 05 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.6.8-%autorelease
- A small patch release to fix empty keys for key-based special cats.
- fix(config): correctly match keyed special categories by value being set by @jmylchreest in https://github.com/hyprwm/hyprlang/pull/89
- @jmylchreest made their first contribution in https://github.com/hyprwm/hyprlang/pull/89
- **Full Changelog**: https://github.com/hyprwm/hyprlang/compare/v0.6.7...v0.6.8
