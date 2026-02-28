Name:           hyprutils
Version:        0.11.0
Release:        %autorelease%{?dist}
Summary:        Small C++ library for utilities used across the Hypr ecosystem

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprutils
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(pixman-1)

%description
hyprutils is a small C++ library used across the Hypr* ecosystem for
various utilities such as memory management, signals, and more.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprutils.so
%{_libdir}/libhyprutils.so.*

%package devel
Summary:        Development files for Small C++ library for utilities used across the Hypr ecosystem
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprutils.

%files devel
%{_includedir}/hyprutils/
%{_libdir}/pkgconfig/hyprutils.pc

%changelog
* Fri Dec 05 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.11.0-%autorelease
- A new update with a few things, breaking ABI.
- logger: don't crash on failing to print to stdout
- cli/argumentParser: improve formatting of description
- cli/argumentParser: allow empty short
- animation: allow/intend for animated vars to be unique pointers by @PaideiaDilemma in https://github.com/hyprwm/hyprutils/pull/93
- i18n: fix typo in sorting entries by @EvilLary in https://github.com/hyprwm/hyprutils/pull/94
- memory/shared: add dynamicPointerCast by @vaxerski in https://github.com/hyprwm/hyprutils/pull/92
- @EvilLary made their first contribution in https://github.com/hyprwm/hyprutils/pull/94
- **Full Changelog**: https://github.com/hyprwm/hyprutils/compare/v0.10.4...v0.11.0
