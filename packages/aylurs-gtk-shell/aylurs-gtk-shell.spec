Name:           aylurs-gtk-shell
Version:        3.1.1
Release:        %autorelease%{?dist}
Summary:        Scaffolding CLI for Astal+Gnim
License:        GPL-3.0-or-later
URL:            https://github.com/Aylur/ags
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz
%global github_com_spf13_cobra_version_version 1.10.1
Source1:        https://github.com/spf13/cobra/archive/refs/tags/v1.10.1.tar.gz#/github_com_spf13_cobra_version-1.10.1.tar.gz

BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  golang
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  gjs

%description
Scaffolding CLI tool for Astal+Gnim projects. Astal is a set of libraries written in Vala/C that makes writing a Desktop Shell easy. Gnim is a library which introduces JSX to GJS. GJS is a JavaScript runtime built on Firefox's SpiderMonkey JavaScript engine and the GNOME platform libraries, the same runtime GNOME Shell runs on.

%prep
%autosetup -n ags-%{version}
tar xf %{SOURCE1}
mv github_com_spf13_cobra_version-1.10.1 github_com_spf13_cobra_version-src

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md

%changelog
* Sun Dec 14 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 3.1.1-%autorelease
- nix: update npm hash
