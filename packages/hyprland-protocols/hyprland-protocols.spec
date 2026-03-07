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
Wayland protocol extensions for Hyprland

This repository exists in an effort to bridge the gap between Hyprland and KDE/Gnome's functionality, as well as allow apps for some extra neat functionality under Hyprland

Since wayland-protocols is slow to change (on top of Hyprland not being allowed to contribute), we have to maintain a set of protocols Hyprland uses to plumb some things / add some useful features

Some of the protocols here also do not belong in w-p, as they are specific to Hyprland

%prep
%autosetup

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
* Sat Oct 04 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.7.0-%autorelease
- tag: v0.7.0, commit: bd153e76f751f150a09328dbdeb5e4fab9d23622
- version: bump to 0.7.0
