
Name:           hyprlock
Version:        0.9.5
Release:        3%{?dist}
Summary:        A gpu-accelerated screen lock for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlock
Source0:        https://github.com/hyprwm/hyprlock/archive/refs/tags/v0.9.5.tar.gz#/hyprlock-0.9.5.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pam)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-egl)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)


%description
Hyprland's simple, yet multi-threaded and GPU-accelerated screen locking utility

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.9.5
Commit:            d75e93f8ee1721d70549d96f4d14bf2948aab70c

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
%{_bindir}/hyprlock
%{_datadir}/hypr/hyprlock.conf
%{_sysconfdir}/pam.d/hyprlock

%changelog
* Sat Apr 18 2026 nett00n <copr@nett00n.org> - 0.9.5-3

- version: bump to 0.9.5
