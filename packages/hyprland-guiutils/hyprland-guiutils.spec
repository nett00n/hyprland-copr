
Name:           hyprland-guiutils
Version:        0.2.1
Release:        2%{?dist}
Summary:        Hyprland GUI utilities
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-guiutils
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel >= 0.1.5
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel >= 0.7.1
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
Tag:               v0.2.1
Commit:            c2e906261142f5dd1ee0bfc44abba23e2754c660

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprgraphics-devel: 0.1.5
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
ninja-build: 1.13.2

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
* Mon Dec 29 2025 nett00n <copr@nett00n.org> - 0.2.1-2

- version: bump to 0.2.1
