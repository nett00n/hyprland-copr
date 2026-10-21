
Name:           neowall
Version:        0.7.2
Release:        4%{?dist}
Summary:        GPU-accelerated live wallpaper engine using GLSL shaders
License:        MIT
URL:            https://github.com/1ay1/neowall
Source0:        https://github.com/1ay1/neowall/archive/refs/tags/v0.7.2.tar.gz#/neowall-0.7.2.tar.gz

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
Tag:               v0.7.2
Commit:            94a996bd1ec8eebdb968bbef9339fa891e22115b

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
* Mon Sep 21 2026 nett00n <copr@nett00n.org> - 0.7.2-4

- release: neowall 0.7.2
- A privacy fix. If you are on any version from 0.5.0 onward, update.
- neowall was opening your microphone. The audio capture path spawns parec
- to read what your speakers are playing, so a wallpaper can react to
- music. It was spawning it with no device argument, and with no device
- parec records the default *source* -- which on a normal desktop is the
- mic, not the speaker loopback. The comment directly above the code said
- "capturing the default monitor", so the intent was always right and the
- implementation quietly did the opposite. If your desktop was telling you
- neowall was using the microphone, it was correct.
- It was also doing this whether or not anything needed audio. The capture
- thread started with the daemon, so a static image wallpaper opened a
- recording stream too.
- What did not happen: none of that audio left your machine. The samples
- land in a stack buffer that is reduced to a volume level, an FFT
- spectrum and a downsampled envelope, then uploaded to a GPU texture to
- be drawn. Nothing is written to disk, nothing is logged, and neowall
- contains no network code at all -- no telemetry, no uploads. Nothing was
- recorded or transmitted. That does not make opening the mic acceptable,
- and it should not have shipped.
- Both halves are fixed. Capture now runs against @DEFAULT_MONITOR@, the
- loopback of your default output, and can no longer reach an input
- device. And it is opt-in: capture only starts if the shader you loaded
- actually reads audio, via an iAudio* uniform, one of the stdlib helpers
- (spectrum, waveform, beat, audioBand) or an iChannel bound to audio.
- Every other wallpaper spawns no parec at all.
- You can confirm it with `pactl list source-outputs` while neowall runs.
- On an affected build there is a parec stream on your input device; here
- there is no stream unless your shader uses audio, and when there is, it
- is attached to your output monitor.
- Affects 0.5.0 through 0.7.1, introduced with the reactive shader
- library. Fixes #84.
