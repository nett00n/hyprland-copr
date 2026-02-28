Name:           hyprwayland-scanner
Version:        0.4.5
Release:        %autorelease%{?dist}
Summary:        A Wayland scanner replacement for Hypr projects

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwayland-scanner
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(pugixml)

%description
hyprwayland-scanner is a Wayland protocol scanner / code generator
used by the Hypr ecosystem to generate C++ protocol bindings.

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
- A few small fixes and patches
- server: fix empty interface arrays
- core: member + designated init and remove redundant cast by @Honkazel in https://github.com/hyprwm/hyprwayland-scanner/pull/14
- Make CMAKE builds arch independent by @NyxTrail in https://github.com/hyprwm/hyprwayland-scanner/pull/16
- nix: use gcc15 by @FridayFaerie in https://github.com/hyprwm/hyprwayland-scanner/pull/17
- @Honkazel made their first contribution in https://github.com/hyprwm/hyprwayland-scanner/pull/14
- @NyxTrail made their first contribution in https://github.com/hyprwm/hyprwayland-scanner/pull/16
- @FridayFaerie made their first contribution in https://github.com/hyprwm/hyprwayland-scanner/pull/17
- **Full Changelog**: https://github.com/hyprwm/hyprwayland-scanner/compare/v0.4.4...v0.4.5
