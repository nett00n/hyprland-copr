Name:           hyprland-qt-support
Version:        0.1.0
Release:        %autorelease%{?dist}
Summary:        A qml style provider for hypr* qt apps
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-qt-support
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  cmake(Qt6Qml)
BuildRequires:  cmake(Qt6Quick)
BuildRequires:  cmake(Qt6QuickControls2)
BuildRequires:  gcc-c++
BuildRequires:  hyprlang-devel
BuildRequires:  ninja-build
BuildRequires:  qt6-rpm-macros

%description
A qml style provider for hypr* qt apps

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.0
Commit:            9d4437011b4f02e60e98a3e36c7fa14bb053b502

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprlang-devel: 0.6.4
ninja-build: 1.13.2
qt6-rpm-macros: 6.10.3

%prep
%autosetup -p1

%build
%cmake -DINSTALL_QMLDIR=%{_libdir}/qt6/qml
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_libdir}/qt6/qml/org/hyprland/
%{_prefix}/lib/libhyprland-quick-style-impl.so
%{_prefix}/lib/libhyprland-quick-style.so

%changelog
* Wed Jan 08 2025 nett00n <copr@nett00n.org> - 0.1.0-1
- version: bump to 0.1.0
