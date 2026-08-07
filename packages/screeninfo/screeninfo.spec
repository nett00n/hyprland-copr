%global debug_package %{nil}

Name:           screeninfo
Version:        0.8.1
Release:        9%{?dist}
Summary:        Fetch location and size of physical screens
BuildArch:      noarch
License:        MIT
URL:            https://github.com/rr-/screeninfo
Source0:        https://github.com/rr-/screeninfo/archive/refs/tags/0.8.1.tar.gz#/screeninfo-0.8.1.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-poetry-core



%description
Python module for fetching location and size of physical screens, useful for placing GUI elements.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l -a screeninfo

%files -f %{pyproject_files}
%doc README.md
%license LICENSE.md

%changelog
* Thu Aug 06 2026 nett00n <copr@nett00n.org> - 0.8.1-9

- Update to 0.8.1
