%global debug_package %{nil}

Name:           hyprland-protocols
Version:        0.8.0
Release:        1%{?dist}
Summary:        Wayland protocol extensions for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprland-protocols
Source0:        https://github.com/hyprwm/hyprland-protocols/archive/refs/tags/v0.8.0.tar.gz#/hyprland-protocols-0.8.0.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build



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
Tag:               v0.8.0
Commit:            044a434ec371f985655389bcef09286b1af3d77c

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

%package devel
Summary:        Development files for Wayland protocol extensions for Hyprland
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprland-protocols.

%files devel
%{_datadir}/%{name}/
%{_datadir}/pkgconfig/%{name}.pc

%changelog
* Fri Oct 16 2026 nett00n <copr@nett00n.org> - 0.8.0-1

- VERSION: bump to 0.8.0
