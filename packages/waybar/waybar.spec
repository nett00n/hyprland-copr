
Name:           waybar
Version:        0.15.0
Release:        1%{?dist}
Summary:        Highly customizable Wayland bar for Sway and Wlroots based compositors
License:        MIT
URL:            https://github.com/Alexays/Waybar.git
Source0:        https://github.com/Alexays/Waybar/archive/refs/tags/0.15.0.tar.gz#/waybar-0.15.0.tar.gz

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
* Mon Jun 01 2026 nett00n <copr@nett00n.org> - 0.15.0-1

- Update to 0.15.0
