
Name:           quickshell
Version:        0.3.1
Release:        3%{?dist}
Summary:        Flexible QtQuick based desktop shell toolkit
License:        LGPL-3.0-or-later
URL:            https://git.outfoxxed.me/quickshell/quickshell.git
Source0:        https://git.outfoxxed.me/quickshell/quickshell/archive/refs/tags/v0.3.1.tar.gz

BuildRequires:  cli11-devel
BuildRequires:  cmake
BuildRequires:  cpptrace-devel
BuildRequires:  gcc-c++
BuildRequires:  glib2-devel
BuildRequires:  glslang-devel
BuildRequires:  libdrm-devel
BuildRequires:  libzstd-devel
BuildRequires:  mesa-libgbm-devel
BuildRequires:  ninja-build
BuildRequires:  pam-devel
BuildRequires:  pipewire-devel
BuildRequires:  pkgconfig(jemalloc)
BuildRequires:  polkit-devel
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtdeclarative-private-devel
BuildRequires:  qt6-qtshadertools-devel
BuildRequires:  wayland-protocols-devel



%description
Quickshell is a toolkit for building status bars, widgets, lockscreens, and other desktop components using QtQuick. It can be used alongside your wayland compositor or window manager to build a complete desktop environment.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.3.1
Commit:            1a4716cde794a59928d9d9fc15f2afc7a95de360

%prep
%autosetup -p1 -n quickshell

%build
%cmake -GNinja -DCRASH_REPORTER=OFF
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/qs
%{_bindir}/quickshell
%{_datadir}/applications/org.quickshell.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.quickshell.svg

%package devel
Summary:        Development files for Flexible QtQuick based desktop shell toolkit
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for quickshell.

%files devel

%changelog
* Fri Aug 21 2026 nett00n <copr@nett00n.org> - 0.3.1-3

- -----BEGIN PGP SIGNATURE-----
- iHUEABYKAB0WIQQBgf+JTzR/zOsGVxBMiKGF+4kwHgUCaoe4DgAKCRBMiKGF+4kw
- HvRhAP9bXanwfCoX0ESaFhqaCsQQf+7WYjDNDQQTo8UIel2Q3wEApi4vMjJ0v/yR
- +kWUNUah79yg1+Cdwb25mbGFcaffRwg=
- =b+fZ
- -----END PGP SIGNATURE-----
