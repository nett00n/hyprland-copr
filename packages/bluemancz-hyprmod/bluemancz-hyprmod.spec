%global debug_package %{nil}

Name:           bluemancz-hyprmod
Version:        0.6.0
Release:        2%{?dist}
Summary:        A native GTK4/libadwaita settings app for Hyprland
BuildArch:      noarch
License:        GPL-3.0-or-later
URL:            https://github.com/BlueManCZ/hyprmod
Source0:        https://github.com/BlueManCZ/hyprmod/archive/refs/tags/v0.6.0.tar.gz#/bluemancz-hyprmod-0.6.0.tar.gz

BuildRequires:  glib2-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip

Requires:       bluemancz-hyprland-config
Requires:       bluemancz-hyprland-monitors
Requires:       bluemancz-hyprland-schema
Requires:       bluemancz-hyprland-socket
Requires:       bluemancz-hyprland-state
Requires:       gtk4
Requires:       libadwaita
Requires:       python3-cairo
Requires:       python3-gobject



%description
HyprMod is a native GTK4/libadwaita settings application for the Hyprland Wayland compositor. It provides live preview of configuration changes over IPC, a Bezier curve editor, a monitor layout editor, a keybind editor, window and workspace rules, autostart management and Lua config support.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprmod-%{version}
sed -i -E 's/"pygobject>=[0-9.]+"/"pygobject"/' pyproject.toml

%build
%pyproject_wheel

%install
%pyproject_install
install -Dm0644 data/applications/io.github.bluemancz.hyprmod.desktop -t %{buildroot}%{_datadir}/applications
install -Dm0644 data/icons/hicolor/scalable/apps/io.github.bluemancz.hyprmod.svg -t %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -Dm0644 data/metainfo/io.github.bluemancz.hyprmod.metainfo.xml -t %{buildroot}%{_metainfodir}
%pyproject_save_files -L -a hyprmod

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE
%{_datadir}/applications/io.github.bluemancz.hyprmod.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.bluemancz.hyprmod.svg
%{_metainfodir}/io.github.bluemancz.hyprmod.metainfo.xml

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.6.0-2

- Update to 0.6.0
