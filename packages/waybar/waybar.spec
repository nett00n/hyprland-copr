
Name:           waybar
Version:        0.15.0
Release:        %autorelease%{?dist}
Summary:        Highly customizable Wayland bar for Sway and Wlroots based compositors
License:        MIT
URL:            https://github.com/Alexays/Waybar
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  catch-devel
BuildRequires:  gcc-c++
BuildRequires:  gpsd-devel
BuildRequires:  jack-audio-connection-kit-devel
BuildRequires:  libdbusmenu-gtk3-devel
BuildRequires:  libevdev-devel
BuildRequires:  libinput-devel
BuildRequires:  libmpdclient-devel
BuildRequires:  libnl3-devel
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pipewire-devel
BuildRequires:  pkgconfig(fmt)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(gtk-layer-shell-0)
BuildRequires:  pkgconfig(gtkmm-3.0)
BuildRequires:  pkgconfig(jsoncpp)
BuildRequires:  pkgconfig(sigc++-2.0)
BuildRequires:  pkgconfig(spdlog)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-cursor)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbregistry)
BuildRequires:  playerctl-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  scdoc
BuildRequires:  sndio-devel
BuildRequires:  systemd
BuildRequires:  upower-devel
BuildRequires:  wireplumber-devel


%description
Highly customizable Wayland bar for Sway and Wlroots based compositors

Note: cava integration is disabled temporary. I am stuck with trying to fix it

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

Build dependencies:
catch-devel: 3.13.0
gcc-c++: 16.0.1
gpsd-devel: 3.27.5
jack-audio-connection-kit-devel: 1.9.22
libdbusmenu-gtk3-devel: 16.04.0
libevdev-devel: 1.13.6
libinput-devel: 1.31.1
libmpdclient-devel: 2.23
libnl3-devel: 3.12.0
meson: 1.10.2
ninja-build: 1.13.2
pipewire-devel: 1.6.3
playerctl-devel: 2.4.1
pulseaudio-libs-devel: 17.0
scdoc: 1.11.3
systemd: 259.5
upower-devel: 1.91.2
wireplumber-devel: 0.5.14

%prep
%autosetup -p1 -n Waybar-%{version}

%build
%meson -Dcava=disabled
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE
%{_bindir}/waybar
%{_mandir}/man5/waybar*.gz
%{_sysconfdir}/xdg/waybar/
%{_userunitdir}/waybar.service

%package devel
Summary:        Development files for Highly customizable Wayland bar for Sway and Wlroots based compositors
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for waybar.

%files devel

%changelog
* Tue Apr 21 2026 nett00n <copr@nett00n.org> - 0.15.0-1
- Update to 0.15.0
