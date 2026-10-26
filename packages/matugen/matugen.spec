%global debug_package %{nil}

Name:           matugen
Version:        4.2.0
Release:        2%{?dist}
Summary:        A Material You and base16 color generation tool with templates
License:        GPL-2.0-or-later
URL:            https://github.com/InioX/matugen
Source0:        https://github.com/InioX/matugen/archive/refs/tags/v4.2.0.tar.gz#/matugen-4.2.0.tar.gz
Source1:        matugen-4.2.0-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  rustc




%description
A Material You and base16 color generation tool with templates. Matugen
generates a color scheme from an image or a color, then renders user
templates (GTK, terminals, Hyprland, bars and more) with the result.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v4.2.0
Commit:            bb27a35d7f9e0f57cf638703f3d8e3182aed0304

%prep
%autosetup -p1
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}

%files
%doc README.md
%license LICENSE
%{_bindir}/matugen

%changelog
* Mon Aug 17 2026 nett00n <copr@nett00n.org> - 4.2.0-2

- chore: Release package matugen version 4.2.0
