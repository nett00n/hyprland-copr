
Name:           hyprpolkitagent
Version:        0.2.0
Release:        1%{?dist}
Summary:        A polkit authentication agent written in QT/QML
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpolkitagent
Source0:        https://github.com/hyprwm/hyprpolkitagent/archive/refs/tags/v0.2.0.tar.gz#/hyprpolkitagent-0.2.0.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(polkit-agent-1)
BuildRequires:  pkgconfig(polkit-qt6-1)
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtquickcontrols2-devel



%description
A simple polkit authentication agent for Hyprland, written in QT/QML

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.2.0
Commit:            0e4492994e211b9af9365f16a9fda35d32e106bb

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_prefix}/lib/systemd/user/hyprpolkitagent.service
%{_prefix}/libexec/hyprpolkitagent
%{_prefix}/share/dbus-1/services/org.hyprland.hyprpolkitagent.service

%changelog
* Wed Sep 09 2026 nett00n <copr@nett00n.org> - 0.2.0-1

- version: bump to 0.2.0
