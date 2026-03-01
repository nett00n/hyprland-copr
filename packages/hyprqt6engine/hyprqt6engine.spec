Name:           hyprqt6engine
Version:        0.1.0
Release:        %autorelease%{?dist}
Summary:        QT6 Theme Provider for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprqt6engine
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  cmake(KF6ColorScheme)
BuildRequires:  cmake(KF6Config)
BuildRequires:  cmake(KF6IconThemes)
BuildRequires:  cmake(Qt6BuildInternals)
BuildRequires:  cmake(Qt6Core)
BuildRequires:  cmake(Qt6Gui)
BuildRequires:  cmake(Qt6GuiPrivate)
BuildRequires:  cmake(Qt6Widgets)
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  qt6-qtwayland-devel
BuildRequires:  qt6-rpm-macros

%description
QT6 Theme Provider for Hyprland. Compatible with KDE, replaces qt6ct.

%prep
%autosetup
sed -i '/target_link_libraries.*hyprqtplugin/i find_package(Qt6 REQUIRED COMPONENTS GuiPrivate)' hyprqtplugin/CMakeLists.txt

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_libdir}/libhyprqt6engine-common.so*
%{_libdir}/qt6/plugins/platformthemes/libhyprqt6engine.so
%{_libdir}/qt6/plugins/styles/libhypr-style.so

%changelog
* Wed Aug 27 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.0-%autorelease
- Initial release of hyprqt6engine
- **Full Changelog**: https://github.com/hyprwm/hyprqt6engine/commits/v0.1.0
