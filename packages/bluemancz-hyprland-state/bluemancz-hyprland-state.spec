%global debug_package %{nil}

Name:           bluemancz-hyprland-state
Version:        0.4.9
Release:        2%{?dist}
Summary:        Live state interface for Hyprland — options, animations, monitors, binds, and devices
BuildArch:      noarch
License:        MIT
URL:            https://github.com/BlueManCZ/hyprland-state
Source0:        https://github.com/BlueManCZ/hyprland-state/archive/refs/tags/v0.4.9.tar.gz#/bluemancz-hyprland-state-0.4.9.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip

Requires:       bluemancz-hyprland-config
Requires:       bluemancz-hyprland-monitors
Requires:       bluemancz-hyprland-schema
Requires:       bluemancz-hyprland-socket



%description
Live state interface for Hyprland: options, animations, monitors, binds and devices, combining the config, schema, monitors and socket libraries.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprland-state-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a hyprland_state

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.4.9-2

- Update to 0.4.9
