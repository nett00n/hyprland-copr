%global debug_package %{nil}

Name:           wlhc
Version:        0.1.1
Release:        4%{?dist}
Summary:        Execute a command when the pointer touches a screen corner
License:        ISC
URL:            https://git.sr.ht/~whynothugo/wlhc
Source0:        https://git.sr.ht/~whynothugo/wlhc/archive/v0.1.1.tar.gz#/wlhc-0.1.1.tar.gz

BuildRequires:  hare
BuildRequires:  hare-ev
BuildRequires:  hare-wayland
BuildRequires:  make
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wlr-protocols)




%description
wlhc (Wayland hot corners) executes a command when the pointer touches a corner of the screen. It needs a compositor implementing wlr_layer_shell_v1.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.1
Commit:            c9508f5849062630a0ef92deea2df340ef416d75

%prep
%autosetup -p1 -n wlhc-v%{version}

%build
make build

%install
install -Dm755 %{name} %{buildroot}%{_bindir}/%{name}

%files
%doc README.md
%license LICENCE.md
%{_bindir}/wlhc

%package devel
Summary:        Development files for Execute a command when the pointer touches a screen corner
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for wlhc.

%files devel

%changelog
* Sat May 30 2026 nett00n <copr@nett00n.org> - 0.1.1-4

- Version 0.1.1
- -----BEGIN PGP SIGNATURE-----
- iIkEABYKADEWIQQSBMqfwv+t7twpYTZ4gHM7nQYoNwUCahrtXBMcaHVnb0B3aHlu
- b3RodWdvLm5sAAoJEHiAczudBig3hw4BAPVtZDdd1YBwQc3VvLFk4BCv7PKHomKg
- /pWvQPIp8lEOAQCl8tFq68Tw35c6ktuloS/tRSxGx7abr+v44nycWY+HCQ==
- =xglR
- -----END PGP SIGNATURE-----
