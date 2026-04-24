
Name:           hyprlock
Version:        0.9.5
Release:        2%{?dist}
Summary:        A gpu-accelerated screen lock for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlock
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel >= 0.1.5
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  hyprwayland-scanner-devel >= 0.4.2
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

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprgraphics-devel: 0.1.5
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
hyprwayland-scanner-devel: 0.4.2
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
%{_bindir}/hyprlock
%{_datadir}/hypr/hyprlock.conf
%{_sysconfdir}/pam.d/hyprlock

%changelog
* Sat Apr 18 2026 nett00n <copr@nett00n.org> - 0.9.5-2

- version: bump to 0.9.5
