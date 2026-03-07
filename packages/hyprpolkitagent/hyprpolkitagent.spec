Name:           hyprpolkitagent
Version:        0.1.3
Release:        %autorelease%{?dist}
Summary:        A polkit authentication agent written in QT/QML
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpolkitagent
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(polkit-agent-1)
BuildRequires:  pkgconfig(polkit-qt6-1)
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-qtquickcontrols2-devel

%description
A simple polkit authentication agent for Hyprland, written in QT/QML

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
%{_prefix}/lib/systemd/user/hyprpolkitagent.service
%{_prefix}/libexec/hyprpolkitagent
%{_prefix}/share/dbus-1/services/org.hyprland.hyprpolkitagent.service

%changelog
* Thu Jul 31 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.3-%autorelease
- tag: v0.1.3, commit: 7e4054410f6d6331b239fea1c659ad6a917fbf6a
- version: bump to 0.1.3
