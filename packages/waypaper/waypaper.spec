%global debug_package %{nil}

Name:           waypaper
Version:        2.8
Release:        8%{?dist}
Summary:        GUI wallpaper manager for Wayland and Xorg Linux systems
BuildArch:      noarch
License:        GPL-3.0-or-later
URL:            https://github.com/anufrievroman/waypaper
Source0:        https://github.com/anufrievroman/waypaper/archive/refs/tags/2.8.tar.gz#/waypaper-2.8.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       gtk3
Requires:       imageio-ffmpeg
Requires:       python3-gobject
Requires:       python3-imageio
Requires:       python3-pillow
Requires:       python3-platformdirs
Requires:       screeninfo


%description
GUI wallpaper setter for Wayland, Xorg, and macOS. It works as a frontend for popular wallpaper backends like swaybg, swww, awww, wallutils, hyprpaper, mpvpaper, gslapper, xwallpaper, feh, linux-wallpaperengine, and macos

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n waypaper-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l -a waypaper

%files -f %{pyproject_files}
%doc README.md
%license LICENSE

%changelog
* Wed Aug 05 2026 nett00n <copr@nett00n.org> - 2.8-8

- Update to 2.8
