Name:           hyprpolkitagent
Version:        0.1.3
Release:        %autorelease%{?dist}
Summary:        A polkit authentication agent written in QT/QML
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpolkitagent
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(polkit-agent-1)
BuildRequires:  pkgconfig(polkit-qt6-1)

%description
A simple polkit authentication agent for Hyprland, written in QT/QML.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md

%changelog
* Thu Jul 31 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.3-%autorelease
- Small patch release
- fix D-bus name by @stradus64 in https://github.com/hyprwm/hyprpolkitagent/pull/30
- nix: use gcc15 by @FridayFaerie in https://github.com/hyprwm/hyprpolkitagent/pull/32
- Rename service-file to 'org.hyprland.hyprpolkitagent.service' by @golgor in https://github.com/hyprwm/hyprpolkitagent/pull/35
- @stradus64 made their first contribution in https://github.com/hyprwm/hyprpolkitagent/pull/30
- @FridayFaerie made their first contribution in https://github.com/hyprwm/hyprpolkitagent/pull/32
- @golgor made their first contribution in https://github.com/hyprwm/hyprpolkitagent/pull/35
- **Full Changelog**: https://github.com/hyprwm/hyprpolkitagent/compare/v0.1.2...v0.1.3
