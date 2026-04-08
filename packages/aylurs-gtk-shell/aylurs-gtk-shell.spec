Name:           aylurs-gtk-shell
Version:        3.1.1
Release:        %autorelease%{?dist}
Summary:        Scaffolding CLI for Astal+Gnim
License:        GPL-3.0-or-later
URL:            https://github.com/Aylur/ags
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        %{name}-%{version}-vendor.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  gjs
BuildRequires:  golang
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  meson
BuildRequires:  ninja-build

%description
Scaffolding CLI tool for Astal+Gnim projects.
Astal is a set of libraries written in Vala/C that makes writing a
Desktop Shell easy. Gnim is a library which introduces JSX to GJS.
GJS is a JavaScript runtime built on Firefox's SpiderMonkey JavaScript
engine and the GNOME platform libraries, the same runtime GNOME Shell runs
on

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

Build dependencies:
gcc-c++: 16.0.1
gjs: 1.88.0
golang: 1.26.1
gtk4-layer-shell-devel: 1.3.0
meson: 1.10.2
ninja-build: 1.13.2

%prep
%autosetup -p1 -n ags-%{version}
pushd cli
tar xf %{SOURCE1}
popd

%build
%meson
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE
%{_prefix}/bin/ags
%{_prefix}/share/ags/

%changelog
* Wed Apr 08 2026 nett00n <copr@nett00n.org> - 3.1.1-1
- Update to 3.1.1
