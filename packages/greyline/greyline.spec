%global debug_package %{nil}

Name:           greyline
Version:        0.8.8
Release:        1%{?dist}
Summary:        Live world-time desktop wallpaper with a day/night terminator
BuildArch:      noarch
License:        GPL-2.0-or-later
URL:            https://github.com/Jotham-LEC/greyline
Source0:        https://github.com/Jotham-LEC/greyline/archive/refs/tags/v0.8.8.tar.gz#/greyline-0.8.8.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       fontconfig
Requires:       python3-pillow
Requires:       python3-tomlkit



%description
A live world-time desktop wallpaper for Wayland and X11, a recreation of the
IBM/ThinkPad World Time Active Desktop with a day/night terminator, per-city
clocks and swappable logos. A systemd user timer runs greyline once a minute: it
renders a PNG per output, hands it to the wallpaper tool you already use, and
exits. Run `greyline init` as your own user; the package installs no systemd units.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.8.8
Commit:            758ebdfd1ad742922604d9d8ece02d6bb0eaa29c

%prep
%autosetup -p1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L -a greyline

%files -f %{pyproject_files}
%doc README.md
%license LICENSE
%license NOTICE
%{_bindir}/greyline

%changelog
* Fri Sep 25 2026 nett00n <copr@nett00n.org> - 0.8.8-1

- Data directories declared; Fedora install documented
- -----BEGIN SSH SIGNATURE-----
- U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgDKk59441ONn2ZQo/4+wkPd6irF
- omrF4/Zi7Y8fRkV/QAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
- AAAAQEFcCK7+BytaWdlcO5BOCfuWGmpUQru6C6FytysoeVAzPCxTwNq4pX42/jScLWWa5k
- NJeY53pm6JyVDfIrufxQI=
- -----END SSH SIGNATURE-----
