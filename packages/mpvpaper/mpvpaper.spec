
Name:           mpvpaper
Version:        1.9
Release:        6%{?dist}
Summary:        A video wallpaper program for wlroots based wayland compositors.
License:        GPL-3.0-or-later
URL:            https://github.com/GhostNaN/mpvpaper
Source0:        https://github.com/GhostNaN/mpvpaper/archive/refs/tags/1.9.tar.gz#/mpvpaper-1.9.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  mpv-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(mpv)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-egl)
BuildRequires:  pkgconfig(wayland-protocols)



%description
mpvpaper is a wallpaper program for wlroots based wayland compositors, such as sway. That allows you to play videos with mpv as your wallpaper.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

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
%{_bindir}/mpvpaper
%{_bindir}/mpvpaper-holder

%package devel
Summary:        Development files for A video wallpaper program for wlroots based wayland compositors.
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for mpvpaper.

%files devel

%changelog
* Wed Jul 29 2026 nett00n <copr@nett00n.org> - 1.9-6

- Update to 1.9
