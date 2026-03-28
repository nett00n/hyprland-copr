Name:           quickshell
Version:        0.2.1
Release:        %autorelease%{?dist}
Summary:        Flexible QtQuick based desktop shell toolkit
License:        LGPL-3.0-or-later
URL:            https://git.outfoxxed.me/quickshell/quickshell
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cli11-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  libdrm-devel
BuildRequires:  mesa-libgbm-devel
BuildRequires:  ninja-build
BuildRequires:  pam-devel
BuildRequires:  pipewire-devel
BuildRequires:  pkgconfig(jemalloc)
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
Tag:               v0.2.1
Commit:            a1a150fab00a93ea983aaca5df55304bc837f51b

%prep
%autosetup -p1 -n quickshell

%build
%cmake -DCRASH_REPORTER=OFF
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
* Sat Oct 11 2025 nett00n <copr@nett00n.org> - 0.2.1-%autorelease
- version: bump to 0.2.1
