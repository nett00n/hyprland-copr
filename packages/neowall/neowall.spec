%global upstream_commit_subject release: neowall 0.11.1
%global upstream_commits 605

Name:           neowall
Version:        0.11.1
Release:        1%{?dist}
Summary:        GPU-accelerated live wallpaper engine using GLSL shaders
License:        MIT
URL:            https://github.com/1ay1/neowall
Source0:        https://github.com/1ay1/neowall/archive/refs/tags/v0.11.1.tar.gz#/neowall-0.11.1.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng16)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-cursor)
BuildRequires:  pkgconfig(wayland-egl)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(x11)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(xrandr)
BuildRequires:  systemd-rpm-macros


Recommends:     pulseaudio-utils


%description
NeoWall is a GPU-accelerated live wallpaper engine for Linux. It renders GLSL (Shadertoy-compatible) shaders, images and a terminal as your desktop background, with transitions, multi-monitor support and audio-reactive shaders. Runs on Wayland (wlr-layer-shell, KDE Plasma, GNOME) and X11.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.11.1
Commit:            d1a7d894f3eff83c51d2f9da41293aa111045a58

%prep
%autosetup -p1

%build
%meson -Dwerror=false
%meson_build

%install
%meson_install

%files
%license LICENSE
%{_bindir}/neowall
%{_datadir}/applications/io.github._1ay1.neowall.desktop
%{_datadir}/bash-completion/completions/neowall
%{_datadir}/fish/vendor_completions.d/neowall.fish
%{_datadir}/icons/hicolor/scalable/apps/io.github._1ay1.neowall.svg
%{_datadir}/metainfo/io.github._1ay1.neowall.metainfo.xml
%{_datadir}/neowall/
%{_datadir}/zsh/site-functions/_neowall
%{_docdir}/neowall/
%{_mandir}/man1/neowall.1.gz
%{_mandir}/man5/neowall.vibe.5.gz
%{_userunitdir}/neowall.service

%package devel
Summary:        Development files for GPU-accelerated live wallpaper engine using GLSL shaders
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for neowall.

%files devel

%changelog
* Sat Nov 21 2026 nett00n <copr@nett00n.org> - 0.11.1-1

- neowall 0.11.1
- -----BEGIN SSH SIGNATURE-----
- U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgo2iVKeZacug0pdwEnjnKu4UZUU
- NOvjJid1J+ygsRcQsAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
- AAAAQGEBVWIgpM27QYJuv7lD/Nu/meOqIGrt5QTKvw56RKeMtCi6n3RQ7wjVTomn6wBHaU
- BBlWJJjk6y/xZkOBqgYAQ=
- -----END SSH SIGNATURE-----
