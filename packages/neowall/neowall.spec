
Name:           neowall
Version:        0.9.0
Release:        1%{?dist}
Summary:        GPU-accelerated live wallpaper engine using GLSL shaders
License:        MIT
URL:            https://github.com/1ay1/neowall
Source0:        https://github.com/1ay1/neowall/archive/refs/tags/v0.9.0.tar.gz#/neowall-0.9.0.tar.gz

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
Tag:               v0.9.0
Commit:            c1452759b2d004b5b16860173d202b9400fea6e4

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
* Sat Nov 14 2026 nett00n <copr@nett00n.org> - 0.9.0-1

- neowall 0.9.0
