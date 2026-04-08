Name:           hyprpolkitagent
Version:        0.1.3
Release:        %autorelease%{?dist}
Summary:        A polkit authentication agent written in QT/QML
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpolkitagent
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
Tag:               v0.1.3
Commit:            7e4054410f6d6331b239fea1c659ad6a917fbf6a

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprutils-devel: 0.7.1
ninja-build: 1.13.2
qt6-qtdeclarative-devel: 6.10.3

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
* Thu Jul 31 2025 nett00n <copr@nett00n.org> - 0.1.3-1
- version: bump to 0.1.3
