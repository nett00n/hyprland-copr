%global debug_package %{nil}

Name:           bluemancz-hyprland-socket
Version:        0.12.2
Release:        2%{?dist}
Summary:        Typed Python library for Hyprland IPC via Unix sockets
BuildArch:      noarch
License:        MIT
URL:            https://github.com/BlueManCZ/hyprland-socket
Source0:        https://github.com/BlueManCZ/hyprland-socket/archive/refs/tags/v0.12.2.tar.gz#/bluemancz-hyprland-socket-0.12.2.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip




%description
Typed Python library for talking to Hyprland over its IPC Unix sockets: send commands, query state and subscribe to compositor events.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprland-socket-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a hyprland_socket

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.12.2-2

- Update to 0.12.2
