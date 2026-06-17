
Name:           hyprshutdown
Version:        0.1.1
Release:        6%{?dist}
Summary:        A graceful shutdown utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprshutdown
Source0:        https://github.com/hyprwm/hyprshutdown/archive/refs/tags/v0.1.1.tar.gz#/hyprshutdown-0.1.1.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glaze-devel
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pixman-1)


%description
A graceful shutdown/logout utility for Hyprland, which prevents apps from
crashing / dying unexpectedly

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.1
Commit:            db1f38b03b173984ae9ed3abeb9750583c9bbd91

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
%{_prefix}/bin/hyprshutdown

%changelog
* Tue May 12 2026 nett00n <copr@nett00n.org> - 0.1.1-6

- version: bump to 0.1.1
