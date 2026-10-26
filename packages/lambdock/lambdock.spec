%global debug_package %{nil}

Name:           lambdock
Version:        0.10.7
Release:        1%{?dist}
Summary:        Wayland desktop dock customizable with GNU Guile Scheme
License:        GPL-3.0-or-later
URL:            https://codeberg.org/jjba23/lambdock.git
Source0:        https://codeberg.org/jjba23/lambdock/archive/refs/tags/v0.10.7.tar.gz#/lambdock-0.10.7.tar.gz

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(gtk4-layer-shell-0)
BuildRequires:  pkgconfig(guile-3.0)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  wayland-devel




%description
Lambdock is a Wayland-native desktop dock built with GTK4,
gtk4-layer-shell and GNU Guile Scheme. It provides dynamic Wayland
top-level window tracking, multi-monitor support, configurable
application launchers, auto-hide animations, GTK CSS themes with
hot-reloading, multiple dock instances, and an embedded Guile Scheme
runtime with an optional interactive REPL. Designed for compositors
implementing wlr-layer-shell, including Hyprland, Sway, River,
Wayfire and Niri.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.10.7
Commit:            152576ec4f65f6b2483475a651bcb33c0a665da3

%prep
%autosetup -p1 -n lambdock

%build
%meson -Dwerror=false
%meson_build

%install
%meson_install

%files
%doc NEWS.org
%doc README.org
%license COPYING
%{_bindir}/lambdock
%{_datadir}/applications/org.jointhefreeworld.lambdock.desktop
%{_datadir}/guile/site/3.0/lambdock/
%{_datadir}/icons/hicolor/scalable/apps/org.jointhefreeworld.lambdock.svg
%{_datadir}/locale/*/LC_MESSAGES/lambdock.mo
%{_datadir}/metainfo/org.jointhefreeworld.lambdock.metainfo.xml

%changelog
* Sun Oct 25 2026 nett00n <copr@nett00n.org> - 0.10.7-1

- chore: Release v0.10.7
- 🤖 Generated with [ECA](https://eca.dev) (deepseek/deepseek-flash)
- Co-Authored-By: eca-agent <git@eca.dev>
