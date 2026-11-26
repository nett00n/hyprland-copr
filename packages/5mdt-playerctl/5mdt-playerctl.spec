
Name:           5mdt-playerctl
Version:        2.6.0
Release:        2%{?dist}
Summary:        MPRIS media player command-line controller (5mdt fork)
License:        LGPL-3.0-or-later
URL:            https://github.com/5mdt/playerctl
Source0:        https://github.com/5mdt/playerctl/archive/refs/tags/v2.6.0.tar.gz#/5mdt-playerctl-2.6.0.tar.gz

BuildRequires:  gcc
BuildRequires:  gobject-introspection-devel
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(bash-completion)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)



Provides:       playerctl
Provides:       playerctl-libs
Conflicts:      playerctl
Conflicts:      playerctl-libs

%description
Fork of playerctl, a command-line utility and library for controlling media
players that implement the MPRIS D-Bus interface (vlc, mpv, RhythmBox, web
browsers, cmus, mpd, spotify and others). Drop-in replacement for Fedora's playerctl.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n playerctl-%{version}

%build
%meson -Dgtk-doc=false -Dtests=false -Dbash-completions=true -Dzsh-completions=true
%meson_build

%install
%meson_install

%files
%doc doc/CHANGELOG.md
%doc README.md
%license LICENSE.md
%{_bindir}/playerctl
%{_bindir}/playerctld
%{_datadir}/bash-completion/completions/playerctl*
%{_datadir}/dbus-1/services/org.mpris.MediaPlayer2.playerctld.service
%{_datadir}/zsh/site-functions/_playerctl
%{_libdir}/girepository-1.0/Playerctl-2.0.typelib
%{_libdir}/libplayerctl.so.2*
%{_mandir}/man1/playerctl.1*

%package devel
Summary:        Development files for MPRIS media player command-line controller (5mdt fork)
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for 5mdt-playerctl.

%files devel
%{_datadir}/gir-1.0/Playerctl-2.0.gir
%{_includedir}/playerctl/
%{_libdir}/libplayerctl.so
%{_libdir}/pkgconfig/playerctl.pc

%changelog
* Thu Nov 26 2026 nett00n <copr@nett00n.org> - 2.6.0-2

- Update to 2.6.0
