%global debug_package %{nil}

Name:           bluemancz-hyprland-monitors
Version:        0.9.2
Release:        2%{?dist}
Summary:        Monitor management utilities for Hyprland
BuildArch:      noarch
License:        MIT
URL:            https://github.com/BlueManCZ/hyprland-monitors
Source0:        https://github.com/BlueManCZ/hyprland-monitors/archive/refs/tags/v0.9.2.tar.gz#/bluemancz-hyprland-monitors-0.9.2.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip

Requires:       bluemancz-hyprland-socket



%description
Monitor management utilities for Hyprland, built on hyprland-socket.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprland-monitors-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a hyprland_monitors

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.9.2-2

- Update to 0.9.2
