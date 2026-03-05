Name:           hyprland-qt-support
Version:        0.1.0
Release:        %autorelease%{?dist}
Summary:        A qml style provider for hypr* qt apps
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-qt-support
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprlang)

%description
A qml style provider for hypr* qt apps

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
* Wed Jan 08 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.0-%autorelease
- Initial release of hyprland-qt-support.
- Shoutout to @outfoxxed for this great piece of software.
- **Full Changelog**: https://github.com/hyprwm/hyprland-qt-support/commits/v0.1.0
