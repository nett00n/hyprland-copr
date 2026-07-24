
Name:           hyprland-guiutils
Version:        0.2.2
Release:        1%{?dist}
Summary:        Hyprland GUI utilities
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-guiutils
Source0:        https://github.com/hyprwm/hyprland-guiutils/archive/refs/tags/v0.2.2.tar.gz#/hyprland-guiutils-0.2.2.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(xkbcommon)



%description
Hyprland GUI utilities (successor to hyprland-qtutils)

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.2.2
Commit:            a16ad89ed5fb4192c966018a80c652de8d96f748

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
%{_prefix}/bin/hyprland-*

%changelog
* Mon Jul 20 2026 nett00n <copr@nett00n.org> - 0.2.2-1

- version: bump to 0.2.2
