%global debug_package %{nil}

Name:           bluemancz-hyprland-schema
Version:        0.8.2
Release:        2%{?dist}
Summary:        Typed Python schema for every Hyprland configuration option
BuildArch:      noarch
License:        MIT
URL:            https://github.com/BlueManCZ/hyprland-schema
Source0:        https://github.com/BlueManCZ/hyprland-schema/archive/refs/tags/v0.8.2.tar.gz#/bluemancz-hyprland-schema-0.8.2.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip




%description
Typed Python schema describing every Hyprland configuration option: names, types, defaults and valid ranges.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hyprland-schema-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a hyprland_schema

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE

%changelog
* Tue Nov 24 2026 nett00n <copr@nett00n.org> - 0.8.2-2

- Update to 0.8.2
