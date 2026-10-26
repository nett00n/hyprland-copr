%global debug_package %{nil}

Name:           pywal16
Version:        3.8.15
Release:        4%{?dist}
Summary:        Generate and change color-schemes on the fly (maintained pywal fork)
BuildArch:      noarch
License:        MIT
URL:            https://github.com/eylles/pywal16
Source0:        https://github.com/eylles/pywal16/archive/refs/tags/3.8.15.tar.gz#/pywal16-3.8.15.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       ImageMagick


Conflicts:      pywal

%description
Pywal16 is the maintained fork of pywal. It generates a color palette from an
image, applies it to running terminals and writes it for other programs to use.
Both pywal and pywal16 install the same `wal` command and cannot be installed
together.

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
%pyproject_save_files -L -a pywal

%files -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md
%license LICENSE.md
%{_bindir}/wal

%changelog
* Mon Oct 26 2026 nett00n <copr@nett00n.org> - 3.8.15-4

- Update to 3.8.15
