Name:           hyprlock
Version:        0.9.2
Release:        %autorelease%{?dist}
Summary:        A gpu-accelerated screen lock for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlock
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(hyprgraphics)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
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

%prep
%autosetup

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
* Thu Oct 02 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.9.2-%autorelease
- tag: v0.9.2, commit: c48279d1e0f0a4399b5a2d56c16f2ec677ba18f8
- version: bump to 0.9.2
