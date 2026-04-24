
Name:           hyprqt6engine
Version:        0.1.0
Release:        2%{?dist}
Summary:        QT6 Theme Provider for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprqt6engine
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  ninja-build
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtbase-private-devel
BuildRequires:  qt6-qtwayland-devel
BuildRequires:  qt6-rpm-macros


%description
QT6 Theme Provider for Hyprland. Compatible with KDE, replaces qt6ct

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.0
Commit:            e8a694d5fc7813cf477f426dce731967e4cf670b

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
ninja-build: 1.13.2
qt6-qtbase-devel: 6.10.3
qt6-qtbase-private-devel: 6.10.3
qt6-qtwayland-devel: 6.10.3
qt6-rpm-macros: 6.10.3

%prep
%autosetup -p1
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
* Tue Aug 26 2025 nett00n <copr@nett00n.org> - 0.1.0-2

- all: initial commit
