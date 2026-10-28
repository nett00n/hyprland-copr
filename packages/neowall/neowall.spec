
Name:           neowall
Version:        0.8.0
Release:        1%{?dist}
Summary:        GPU-accelerated live wallpaper engine using GLSL shaders
License:        MIT
URL:            https://github.com/1ay1/neowall
Source0:        https://github.com/1ay1/neowall/archive/refs/tags/v0.8.0.tar.gz#/neowall-0.8.0.tar.gz

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
BuildRequires:  pkgconfig(x11)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(xrandr)


Recommends:     pulseaudio-utils


%description
NeoWall is a GPU-accelerated live wallpaper engine for Linux. It renders GLSL (Shadertoy-compatible) shaders, images and a terminal as your desktop background, with transitions, multi-monitor support and audio-reactive shaders. Runs on Wayland (wlr-layer-shell, KDE Plasma, GNOME) and X11.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.8.0
Commit:            843e112cb3a1dcd2b25a886462bf98b81f27eb4e

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
%{_datadir}/applications/neowall.desktop
%{_datadir}/icons/hicolor/scalable/apps/neowall.svg
%{_datadir}/neowall/
%{_docdir}/neowall/
%{_prefix}/lib/systemd/user/neowall.service

%package devel
Summary:        Development files for GPU-accelerated live wallpaper engine using GLSL shaders
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for neowall.

%files devel

%changelog
* Mon Oct 26 2026 nett00n <copr@nett00n.org> - 0.8.0-1

- release: neowall 0.8.0
- Smoother animation, and a rewritten core loop.
- Wallpapers that stutter after running a while. iTime is a float32, and
- the shader clock was only reset while the wallpaper was hidden. One that
- stays on screen kept growing: after a day iTime moves in 7.8 ms steps,
- after ten days in 62.5 ms steps, so the animation updates ~16 times a
- second however fast it renders. A wallpaper visible for 2 hours now
- resets its clock behind a short cross-fade.
- Exact frame timing on Wayland. iTime used to be read when drawing
- started, so its step wobbled with the draw start. Each frame is now
- stamped with the vblank it is shown at (presentation-time feedback), so
- iTime advances by exactly one refresh per refresh. iTimeDelta matches.
- X11 keeps the old clock-based time.
- Load and input uniforms (iCpu, iRam, key/mouse energy, ...) ease toward
- each 4 Hz sample instead of stepping.
- garden: the pollen and fireflies no longer teleport when the wind
- changes, and a frame costs half as much at 3440x1440.
- Runtime: the event loop is a small Elm-style runtime, and the CLI talks
- to the daemon over a unix socket. A chatty terminal wallpaper no longer
- wakes the loop on every read.
- Fixes: parec, nvidia-smi and the terminal shell inherited the daemon's
- blocked signals and ignored SIGPIPE, so they couldn't be stopped and
- outlived neowall. Also a use-after-free at shutdown, and data races
- found with tsan.
