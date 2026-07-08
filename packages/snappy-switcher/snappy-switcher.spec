%global debug_package %{nil}

Name:           snappy-switcher
Version:        4.0.0
Release:        14%{?dist}
Summary:        alt-tab switch window for wayland compositor
License:        GPL-3.0
URL:            https://github.com/OpalAayan/snappy-switcher
Source0:        https://github.com/OpalAayan/snappy-switcher/archive/refs/tags/v4.0.0.tar.gz#/snappy-switcher-4.0.0.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(json-c)
BuildRequires:  pkgconfig(librsvg-2.0)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-cursor)
BuildRequires:  pkgconfig(wayland-scanner)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  wayland-protocols-devel



%description
The window switcher that actually understands your workflow

Pure C · Wayland Layer Shell · Zero dependencies on Electron or GTK runtimes

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v4.0.0
Commit:            c2823cdd006c36d50c1e625dccbbc6685b43f1f4

%prep
%autosetup -p1
sed -i 's/BINDIR = \$(PREFIX)\/bin/BINDIR = $(DESTDIR)$(PREFIX)\/bin/; s/DATADIR = \$(PREFIX)\/share/DATADIR = $(DESTDIR)$(PREFIX)\/share/; s/DOCDIR = \$(PREFIX)\/share/DOCDIR = $(DESTDIR)$(PREFIX)\/share/; s/SYSCONFDIR = \/etc/SYSCONFDIR = $(DESTDIR)\/etc/' Makefile

%build
make %{?_smp_mflags}

%install
%make_install PREFIX=%{_prefix}

%files
%doc README.md
%{_bindir}/snappy-install-config
%{_bindir}/snappy-switcher
%{_bindir}/snappy-wrapper
%{_datadir}/snappy-switcher/themes/*.ini
%{_docdir}/snappy-switcher/config.ini.example
%{_sysconfdir}/xdg/snappy-switcher/config.ini

%changelog
* Wed Jun 03 2026 nett00n <copr@nett00n.org> - 4.0.0-14

- fix(build): resolve wayland-protocols path for Fedora
