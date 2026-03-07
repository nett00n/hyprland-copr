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
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  qt6-rpm-macros

%description
A qml style provider for hypr* qt apps

%prep
%autosetup

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
* Wed Jan 08 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.0-%autorelease
- tag: v0.1.0, commit: 9d4437011b4f02e60e98a3e36c7fa14bb053b502
- version: bump to 0.1.0
