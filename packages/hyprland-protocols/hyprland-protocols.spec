%global debug_package %{nil}
Name:           hyprland-protocols
Version:        0.7.0
Release:        %autorelease%{?dist}
Summary:        Wayland protocol extensions for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-protocols
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  meson

%description
hyprland-protocols

Wayland protocol extensions for Hyprland.

This repository exists in an effort to bridge the gap between Hyprland
and KDE/Gnome's functionality, as well as allow apps for some extra neat
functionality under Hyprland.

Since wayland-protocols is slow to change (on top of Hyprland not being
allowed to contribute), we have to maintain a set of protocols Hyprland
uses to plumb some things / add some useful features.

Some of the protocols here also do not belong in w-p, as they are specific
to Hyprland.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.7.0
Commit:            bd153e76f751f150a09328dbdeb5e4fab9d23622

Build dependencies:
meson: 1.10.2

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE

%package devel
Summary:        Development files for Wayland protocol extensions for Hyprland
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprland-protocols.

%files devel
%{_datadir}/%{name}/
%{_datadir}/pkgconfig/%{name}.pc

%changelog
* Sat Oct 04 2025 nett00n <copr@nett00n.org> - 0.7.0-1
- version: bump to 0.7.0
