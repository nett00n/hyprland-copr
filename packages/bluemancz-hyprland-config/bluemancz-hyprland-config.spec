%global debug_package %{nil}

Name:           bluemancz-hyprland-config
Version:        0.9.21
Release:        2%{?dist}
Summary:        Round-trip parser and editor for Hyprland configuration files
BuildArch:      noarch
License:        MIT
URL:            https://github.com/BlueManCZ/hyprland-config
Source0:        https://github.com/BlueManCZ/hyprland-config/archive/refs/tags/v0.9.21.tar.gz#/bluemancz-hyprland-config-0.9.21.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip

Requires:       bluemancz-hyprland-schema
Requires:       lua



%description
Round-trip parser and editor for Hyprland configuration files. Reads and rewrites hyprland.conf and the Lua config format while preserving comments and layout. Needs a Lua interpreter to read Lua configs.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprland-config-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a hyprland_config

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.9.21-2

- Update to 0.9.21
