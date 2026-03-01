Name:           hyprcursor
Version:        0.1.13
Release:        %autorelease%{?dist}
Summary:        A library and toolkit for the Hyprland cursor format
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprcursor
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(librsvg-2.0)
BuildRequires:  pkgconfig(libzip)
BuildRequires:  pkgconfig(tomlplusplus)

%description
FIXME

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprcursor-util
%{_libdir}/libhyprcursor.so*

%package devel
Summary:        Development files for A library and toolkit for the Hyprland cursor format
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprcursor.

%files devel
%{_includedir}/hyprcursor.hpp
%{_includedir}/hyprcursor/
%{_libdir}/pkgconfig/hyprcursor.pc

%changelog
* Thu Jul 31 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.13-%autorelease
- A small release fixing resizing algorithms for png cursors
- core: fix png resampling
- docs: updated MAKING_THEMS.md by @sarojregmi200 in https://github.com/hyprwm/hyprcursor/pull/86
- nix: use gcc15 by @FridayFaerie in https://github.com/hyprwm/hyprcursor/pull/91
- @sarojregmi200 made their first contribution in https://github.com/hyprwm/hyprcursor/pull/86
- @FridayFaerie made their first contribution in https://github.com/hyprwm/hyprcursor/pull/91
- **Full Changelog**: https://github.com/hyprwm/hyprcursor/compare/v0.1.12...v0.1.13
